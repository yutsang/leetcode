import os
import time
import re
import pandas as pd
from datetime import datetime, timedelta
from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException
import configparser

# Read configuration
config = configparser.ConfigParser()
config.read('config.cfg')

# Get configuration values
driver_path = config.get('Settings', 'driverpath')
username = config.get('Credentials', 'username')
password = config.get('Credentials', 'password')

# Initialize the ChromeDriver
driver = webdriver.Chrome(driver_path)

def parse_relative_time(time_string):
    units = {'minute': 60, 'hour': 3600, 'day': 86400, 'week': 604800, 'month': 2628000, 'year': 31536000}
    total_seconds = 0
    matches = re.findall(r'(\d+)\s+(minute|hour|day|week|month|year)s?', time_string)
    for amount, unit in matches:
        total_seconds += int(amount) * units[unit]
    return timedelta(seconds=total_seconds)

def get_most_recent_timestamp(file_path):
    creation_time = os.path.getctime(file_path)
    modification_time = os.path.getmtime(file_path)
    return datetime.fromtimestamp(max(creation_time, modification_time))

def scrape_page(url):
    driver.get(url)
    try:
        WebDriverWait(driver, 5).until(
            EC.presence_of_element_located((By.XPATH, "//div[@id='submission-list-app']//table"))
        )
    except TimeoutException:
        print(f"Timeout waiting for page to load: {url}")
        return ""
    return driver.page_source

def collect_all_submissions():
    page = 1
    all_data = []
    while True:
        url = f"https://leetcode.com/submissions/#/{page}"
        page_content = scrape_page(url)
        if not page_content:
            print(f"Empty page encountered: {url}")
            break

        soup = BeautifulSoup(page_content, 'html.parser')
        table = soup.find('table', class_='table')
        if table:
            for row in table.find_all('tr')[1:]:
                cols = row.find_all('td')
                if len(cols) == 5:
                    time_submitted = cols[0].text.strip()
                    question_link = cols[1].find('a')
                    question = question_link.text.strip()
                    question_path = question_link['href']
                    status = cols[2].text.strip()
                    runtime = cols[3].text.strip()
                    language = cols[4].text.strip()
                    all_data.append([time_submitted, question, f"https://leetcode.com{question_path}", status, runtime, language])

            print(f"Successfully parsed page {page}")

        if "No more submissions." in page_content:
            print("Reached the end of submissions.")
            break

        page += 1
        time.sleep(2)

    df = pd.DataFrame(all_data, columns=['Time Submitted', 'Question', 'Question URL', 'Status', 'Runtime', 'Language'])
    df.to_csv('leetcode_submissions.csv', index=False)
    print("Saved all submissions to leetcode_submissions.csv")

def login_to_leetcode():
    driver.get("https://leetcode.com/accounts/github/login/?next=%2F")
    continue_button = WebDriverWait(driver, 10).until(
        EC.element_to_be_clickable((By.XPATH, "//button[contains(text(), 'Continue')]"))
    )
    continue_button.click()

    try:
        username_field = WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.ID, "login_field"))
        )
        password_field = driver.find_element(By.ID, "password")
        username_field.send_keys(username)
        password_field.send_keys(password)
        login_button = driver.find_element(By.NAME, "commit")
        login_button.click()
        print("Logged in successfully.")
    except TimeoutException:
        print("Timeout while waiting for the login fields.")
        driver.quit()
        exit()

    time.sleep(5)

def main():
    login_to_leetcode()
    collect_all_submissions()

    submission_records_filename = 'leetcode_submissions.csv'
    recent_datetime = get_most_recent_timestamp(submission_records_filename)

    submission_records = pd.read_csv(submission_records_filename)
    leetcode_problems = pd.read_csv('leetcode_problems.csv')

    submission_records.insert(1, 'Finished Date', 0)
    submission_records['Finished Date'] = submission_records['Time Submitted'].apply(
        lambda x: (recent_datetime - parse_relative_time(x)).date()
    )
    submission_records = submission_records.drop(columns='Time Submitted').sort_values(by='Finished Date', ascending=False)
    submission_records = submission_records[submission_records['Status'] == 'Accepted'].drop_duplicates(subset='Question URL', keep='first')

    submission = pd.merge(submission_records, leetcode_problems, left_on='Question', right_on='Title', how='left').drop_duplicates(subset='Question')

    os.makedirs('submissions', exist_ok=True)

    for index, row in submission.head(10).iterrows():
        question_number = row.get('Question Number')
        title_slug = row['Title Slug']
        if not question_number or not os.path.exists(f"submissions/{question_number}_{title_slug}.py"):
            question_number, code, submission_url = extract_question_info(driver, row['Question URL'])
            if question_number and code:
                file_name = f"submissions/{question_number}_{title_slug}.py"
                with open(file_name, 'w') as f:
                    f.write(code)
                print(f"Created file: {file_name}")
                submission.at[index, 'Question Number'] = question_number
                submission.at[index, 'Submission Url'] = submission_url
            else:
                print(f"Failed to extract information for: {row['Question URL']}")
        else:
            print(f"File already exists for question {question_number}: {title_slug}")

        time.sleep(2)

    markdown_format = """
| Question # | Finished Date | Title | Submission | Difficulty |
|:---:|:---:|:---:|:---:|:---:|
"""
    for index, row in submission.iterrows():
        markdown_format += f"|{row['Question Number']}|{row['Finished Date']}|[{row['Question']}]({row['Question URL']+'/description/'})|[Python](https://github.com/yutsang/leetcode/blob/main/submissions/{row['Question Number']}_{row['Title Slug']}.py)|{row['Difficulty']}|\n"

    with open('README.md', 'w') as file:
        file.write(markdown_format)

    print("Markdown file generated successfully.")
    driver.quit()

if __name__ == "__main__":
    main()
