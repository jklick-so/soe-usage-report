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
            By default, this Python script uses filters to strip out any PII or CI data.
            For more details on filters, see https://api.stackexchange.com/docs/filters

    Returns:
        items (list): this is a list of dictionaries containing the requested data
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
    tag_contributors, question_contributors, answer_contributors = create_contributor_lists(
        questions, answers)
    asked_and_answered = [value for value in question_contributors if value in answer_contributors]
    all_contributors = question_contributors + answer_contributors
    deduped_contributors = dict.fromkeys(all_contributors)

    # count the amount of users in each list
    user_count = len(users)
    asker_count = len(question_contributors)
    answerer_count = len(answer_contributors)
    asked_and_answered_count = len(asked_and_answered)
    contributor_count = len(deduped_contributors)
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
    print()

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

    for question in questions:
        user_id = validate_user_id(question)
        question_contributors = add_user_to_list(user_id, question_contributors)
        for tag in question['tags']:
            tag_index = find_dict_in_list(tag, 'tag', tag_contributors)
            if tag_index is None:
                tag_contributors.append(
                    {
                        'tag': tag,
                        'askers': [user_id],
                        'answerers': []
                    }
                )
            else:
                tag_contributors[tag_index]['askers'] = add_user_to_list(
                user_id, tag_contributors[tag_index]['askers'])

    for answer in answers:
        user_id = validate_user_id(question)
        answer_contributors = add_user_to_list(user_id, answer_contributors)
        question = find_dict_in_list(answer['question_id'], 'question_id', questions, False)
        for tag in question['tags']:
            tag_index = find_dict_in_list(tag, 'tag', tag_contributors)
            tag_contributors[tag_index]['answerers'] = add_user_to_list(
                user_id, tag_contributors[tag_index]['answerers'])

    return tag_contributors, question_contributors, answer_contributors


def create_tag_report(questions, answers, tag_contributors):

    tag_metrics = {}
    for question in questions:
        for tag in question['tags']:
            try:
                tag_metrics[tag]['question_count'] += 1
                tag_metrics[tag]['view_count'] += question['view_count']
            except KeyError:
                tag_metrics[tag] = {
                    'question_count': 1,
                    'view_count': question['view_count'],
                    'answer_count': 0
                }

    for answer in answers:
        question = find_dict_in_list(answer['question_id'], 'question_id', questions, False)
        for tag in question['tags']:
            tag_metrics[tag]['answer_count'] += 1

    tags_sorted_by_view_count = sorted(
        tag_metrics.items(), key = lambda x: x[1]['view_count'], reverse=True)

    print("TOP TAGS")
    csv_data = []
    for i, tag_data in enumerate(tags_sorted_by_view_count):
        tag = tag_data[0]
        view_count = tag_data[1]['view_count']
        question_count = tag_data[1]['question_count']
        answer_count = tag_data[1]['answer_count']

        contributor_data = find_dict_in_list(tag, 'tag',tag_contributors, False)
        askers_count = len(contributor_data['askers'])
        answerers_count = len(contributor_data['answerers'])
        csv_row = [tag, view_count, question_count, answer_count, askers_count, answerers_count]
        csv_data.append(csv_row)

        if i < 20:
            output_text = f"{tag} | page views: {view_count} | questions: {question_count} | " \
                f"answers: {answer_count} | unique askers: {askers_count} | " \
                f"unique answerers: {answerers_count}"
            print(output_text)

    csv_header = ['tag', 'page views', 'question count', 'answer count', 'unique askers', \
            'unique answerers']
    csv_file_name = 'tag_metrics.csv'
    write_csv(csv_file_name, csv_header, csv_data)


def add_user_to_list(user_id, user_list):
    """Checks to see if a user_id already exists is in a list. If not, it adds the new user_id to 
    the list.

    Args:
        user_id (int): the ID of the user in Stack Overflow
        user_list (list): current user list

    Returns:
        list: updated user list
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
            dictionary. When False, the function returns the contents of the dictionary.
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

    try:
        user_id = item['owner']['account_id']
    except KeyError: # If an owner account has been deleted, user_id will not exist
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
    get_items(QUESTIONS_ENDPOINT, "!)QCGvppz4*yNaovd_i*d5VRH")
    get_items(ANSWERS_ENDPOINT, "!)Q5ZKXZC3gAkrZ83hw9t3b47")
    get_items(USERS_ENDPOINT, "!0Z-LvhH.I(HSQL-9.EeSLuce2")
    create_usage_report()
