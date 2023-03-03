"""This script is meant for demonstration purposes only. Please adhere to company policies for API
key management, coding standards, and best practices in your environment.

Outputs of this script include:
  * A console print out of usage metrics, which can be copy-pasted
  * A CSV file with an extended list of tag metrics
  * Three JSON files with raw data for questions, answers, and users

To get started, change the BASE_API_URL and APIKEY variables to the correct values.
You may also need to install the Requests library primary to running the script:
https://requests.readthedocs.io/en/latest/user/install/#install
"""

import csv
import json
import time
import requests

BASE_API_URL = "https://YOUR.INSTANCE.URL/api/2.3/"
APIKEY = "YOUR_API_KEY"
QUESTIONS_ENDPOINT = "questions"
ANSWERS_ENDPOINT = "answers"
USERS_ENDPOINT = "users"


def get_items(endpoint, filter_id=''):
    """This function will use the Stack Overflow Enterprise API to get all items of a particular
    type, indicated by the endpoint argument.

    Args:
        endpoint (string): the API endpoint containing the data to read. No leading "/" is required
            since this is already taken care of in the BASE_API_URL variable
        filter_id (string): this is an optional filter parameter that can be added to the API call.
            By default, this Python script uses filters to strip out any PII or CI data, as well as
            include some useful fields that are hidden by default.
            For more details on filters, see https://api.stackexchange.com/docs/filters

    Returns:
        items (list): a list of dictionaries, each containing an object of the requested type
    """

    # Establish API call parameters
    endpoint_url = BASE_API_URL + endpoint
    params = {
        'page': 1,
        'pagesize': 100,
    }

    if filter_id:
        params['filter'] = filter_id

    headers = {
    'X-API-Key': APIKEY
    }

    # Keep performing API calls until all items are received
    items = []
    while True:
        print(f"Getting page {params['page']} of /{endpoint}")
        response = requests.get(endpoint_url, headers=headers, params=params)

        if response.status_code != 200:
            print(f"/{endpoint} API call failed with status code: {response.status_code}.")
            print(response.text)
            break

        items_data = response.json().get('items')
        items += items_data

        if not response.json().get('has_more'):
            break

        # If the endpoint gets overloaded, it will send a backoff request in the response
        # Failure to backoff will result in a 502 Error
        if response.json().get('backoff'):
            print("Backoff request received from endpoint. Waiting 15 seconds...")
            time.sleep(15)

        params['page'] += 1

    write_json(items, endpoint+".json")


def write_json(data, file_name):

    with open(file_name, 'w') as f:
        json.dump(data, f)

    print("\n*********************************************************")
    print(f"{file_name} has been saved to the current directory.")
    print("*********************************************************\n")


def create_usage_report():

    users = read_json(USERS_ENDPOINT+".json")
    questions = read_json(QUESTIONS_ENDPOINT+".json")
    answers = read_json(ANSWERS_ENDPOINT+".json")

    # create lists of anonymized users based on different criteria
    tag_contributors, question_contributors, answer_contributors, comment_contributors = \
        create_contributor_lists(questions, answers)
    asked_and_answered = [value for value in question_contributors if value in answer_contributors]
    all_unique_contributors = set(
        question_contributors + answer_contributors + comment_contributors)

    # count the amount of users in each list
    user_count = len(users)
    asker_count = len(question_contributors)
    answerer_count = len(answer_contributors)
    asked_and_answered_count = len(asked_and_answered)
    contributor_count = len(all_unique_contributors)
    users_with_badges = calculate_user_badges(users)

    # calculate post and tag metrics
    question_count = len(questions)
    answer_count = len(answers)

    total_view_count = 0
    for question in questions:
        total_view_count += question['view_count']

    # print metrics to terminal
    print()
    print("************")
    print("USAGE REPORT")
    print("************")
    print(f"Total registered users: {user_count}")
    print(f"Total users who asked questions: {asker_count}")
    print(f"Total users who answered questions: {answerer_count}")
    print(f"Total users who asked AND answered: {asked_and_answered_count}")
    print(f"Total users who asked OR answered: {contributor_count}")
    print(f"Total users with participation badges: {users_with_badges}")
    print()
    print(f"Total questions: {question_count}")
    print(f"Total answers: {answer_count}")
    print(f"Total page views across questions: {total_view_count}")

    create_tag_report(questions, answers, tag_contributors)


def read_json(file_name):

    with open(file_name, 'r') as f:
        data = json.loads(f.read())

    return data


def create_contributor_lists(questions, answers):
    """This function creates lists of contributors (i.e. users who have either asked or answered
    a question), both generally and for each individual tag. Other parts of this Python script use
    these lists to count the number of contributors for reporting purposes.

    Args:
        questions (list): a list of dictionaries, each dictionary containing data for a question
        answers (list): a list of dictionaries, each dictionary containing data for an answer

    Returns:
        tag_contributors (list): a list of dictionaries, each containing a list of unique (deduped)
            user IDs of those users who have asked or answered at least one question on Stack
        question_contributors (list): a list of unique (deduped) user IDs of those users who have
            asked at least one question on Stack
        answer_contributors (list): a list of unique (deduped) user IDs of those users who have
            answered at least one question on Stack
    """
    tag_contributors = []
    question_contributors = []
    answer_contributors = []
    comment_contributors = []

    for question in questions:
        asker_id = validate_user_id(question)
        question_contributors = add_user_to_list(asker_id, question_contributors)
        for tag in question['tags']:
            while True:
                tag_index = find_dict_in_list(tag, 'tag', tag_contributors)
                if tag_index is None:
                    tag_contributors.append(
                        {
                            'tag': tag,
                            'askers': [],
                            'answerers': [],
                            'commenters': []
                        }
                    )
                else:
                    break

            tag_contributors[tag_index]['askers'] = add_user_to_list(
                asker_id, tag_contributors[tag_index]['askers']
            )

            if question.get('comments'):
                for comment in question['comments']:
                    commenter_id = validate_user_id(comment)
                    comment_contributors = add_user_to_list(commenter_id, comment_contributors)
                    tag_contributors[tag_index]['commenters'] = add_user_to_list(
                        commenter_id, tag_contributors[tag_index]['commenters']
                    )

    for answer in answers:
        answerer_id = validate_user_id(answer)
        answer_contributors = add_user_to_list(answerer_id, answer_contributors)
        question = find_dict_in_list(answer['question_id'], 'question_id', questions, False)

        for tag in question['tags']:
            tag_index = find_dict_in_list(tag, 'tag', tag_contributors)
            tag_contributors[tag_index]['answerers'] = add_user_to_list(
                answerer_id, tag_contributors[tag_index]['answerers'])

            if answer.get('comments'):
                for comment in answer['comments']:
                    commenter_id = validate_user_id(comment)
                    comment_contributors = add_user_to_list(commenter_id, comment_contributors)
                    tag_contributors[tag_index]['commenters'] = add_user_to_list(
                        commenter_id, tag_contributors[tag_index]['commenters']
                    )

    return tag_contributors, question_contributors, answer_contributors, comment_contributors


def create_tag_report(questions, answers, tag_contributors):

    tag_metrics = {}
    for question in questions:
        for tag in question['tags']:
            try:
                tag_metrics[tag]['question_count'] += 1
            except KeyError: # if tag doesn't have a dictionary created yet, initialize one
                tag_metrics[tag] = {
                    'view_count': 0,
                    'unique_askers': 0,
                    'unique_answerers': 0,
                    'unique_commenters': 0,
                    'unique_contributors': 0,
                    'question_count': 1,
                    'question_upvotes': 0,
                    'question_downvotes': 0,
                    'question_comments': 0,
                    'questions_no_answers': 0,
                    'questions_accepted_answer': 0,
                    'answer_count': 0,
                    'answer_upvotes': 0,
                    'answer_downvotes': 0,
                    'answer_comments': 0,
                }
            tag_metrics[tag]['view_count'] += question['view_count']
            tag_metrics[tag]['question_upvotes'] += question['up_vote_count']
            tag_metrics[tag]['question_downvotes'] += question['down_vote_count']

            try:
                tag_metrics[tag]['question_comments'] += len(question['comments'])
            except KeyError: # if there are no comments, a KeyError will be produced
                pass

            if question['answer_count'] == 0:
                tag_metrics[tag]['questions_no_answers'] += 1
            if question['is_answered'] == True:
                tag_metrics[tag]['questions_accepted_answer'] += 1

            tag_contributor_data = find_dict_in_list(tag, 'tag', tag_contributors, False)
            tag_metrics[tag]['unique_askers'] = len(tag_contributor_data['askers'])
            tag_metrics[tag]['unique_answerers'] = len(tag_contributor_data['answerers'])
            tag_metrics[tag]['unique_commenters'] = len(tag_contributor_data['commenters'])
            tag_metrics[tag]['unique_contributors'] = len(set(
                tag_contributor_data['askers'] + tag_contributor_data['answerers'] +
                tag_contributor_data['commenters']
                ))

    for answer in answers:
        question = find_dict_in_list(answer['question_id'], 'question_id', questions, False)
        for tag in question['tags']:
            tag_metrics[tag]['answer_count'] += 1
            tag_metrics[tag]['answer_upvotes'] += answer['up_vote_count']
            tag_metrics[tag]['answer_downvotes'] += answer['down_vote_count']
            try:
                tag_metrics[tag]['answer_comments'] += len(answer['comments'])
            except KeyError: # if there are no comments, a KeyError will be produced
                pass

    tags_sorted_by_view_count = sorted(
        tag_metrics.items(), key = lambda x: x[1]['view_count'], reverse=True)

    csv_data = []
    for tag_data in tags_sorted_by_view_count:
        tag = tag_data[0]
        csv_row = [tag] + list(tag_data[1].values())
        csv_data.append(csv_row)

    csv_header = ['Tag', 'Aggregate Page Views', 'Unique Askers', 'Unique Answerers',
                  'Unique Commenters', 'Unique Contributors','Question Count', 'Question Upvotes',
                  'Question Downvotes', 'Question Comments', 'Questions Without Answers',
                  'Questions With Accepted Answers', 'Answer Count', 'Answer Upvotes',
                  'Answer Downvotes', 'Answer Comments']
    csv_file_name = 'tag_metrics.csv'
    write_csv(csv_file_name, csv_header, csv_data)


def add_user_to_list(user_id, user_list):
    """Checks to see if a user_id already exists is in a list. If not, it adds the new user_id to 
    the list.

    Args:
        user_id (int): the unique user ID of a particular user in Stack Overflow
        user_list (list): current user list

    Returns:
        user_list (list): updated user list
    """
    if user_id not in user_list:
        user_list.append(user_id)
    return user_list


def find_dict_in_list(id, key, list_of_dicts, return_index=True):
    """This Python script leverages different lists of dictionaries. Finding certain dictionaries
    in those lists can be a common task. Sometimes the script is looking for the data in the
    dictionary; othertimes, it just wants the index of the dictionary. This function can
    cater to both scenarios using the 'return_index' parameter. If the search doesn't produce
    a result, 'None' will be returned.

    Args:
        id (string): the dictionary value that is being searched for
        key (string): the dictionary key that will contain the value searched for
        list_of_dicts (list): the list of dictionaries being searched through
        return_index (bool, optional): When True, the function returns the list index of the
            dictionary. When False, the function returns the whole dictionary.
            Defaults to True.

    Returns:
        int, dict, or None: Depending on the 'return_index' parameter, an integer or dictionary
            will be returned. However, if the search yields no result, None will be returned.
    """
    if return_index:
        search_result = next((i for i, dict in enumerate(list_of_dicts) if dict[key] == id), None)
    else:
        search_result = next((dict for dict in list_of_dicts if dict[key] == id), None)

    return search_result


def calculate_user_badges(users):

    users_with_badges = 0
    for user in users:
        if user['badge_counts']['bronze'] > 0:
            users_with_badges += 1

    return users_with_badges


def validate_user_id(item):
    """This function looks at an item (e.g. question, answer, or comment) and validates if the user
    still exists. For further context, when a user is deleted from the platform, their content will
    remain behind, but it will no longer be attributed to anyone in particular. If a user_id does
    not exist for the user, a user_id of "unknown" will be assigned instead.

    Args:
        item (dict): the dictionary for a question, answer, or comment

    Returns:
        user_id (string): the user ID to whom the content is attributed, or "unknown" if the user
            no longer exists
    """
    try:
        user_id = item['owner']['user_id']
    except KeyError:
        user_id = 'unknown'

    return user_id


def write_csv(file_name, header, data):

    with open(file_name, 'w', encoding='UTF8', newline='') as f:
        writer = csv.writer(f)
        writer.writerow(header)
        for item in data:
            writer.writerow(item)

    print("\n*************************************************************************")
    print(f"Extended metrics were saved to '{file_name}' in the current directory")
    print("*************************************************************************\n")


if __name__ == '__main__':
    get_items(QUESTIONS_ENDPOINT, "!t-MolHjKtPLQXQGxGwuxRiz2FAIbzBW")
    get_items(ANSWERS_ENDPOINT, "!1zhxWdTMzIx6vivJYIYoB")
    get_items(USERS_ENDPOINT, "!LnO)*TtSsJGGD5.dHo0NYN")
    create_usage_report()
