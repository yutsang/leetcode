import os
import time
import pandas as pd
from datetime import datetime, timedelta
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException
from bs4 import BeautifulSoup
import re
import configparser
import warnings

warnings.filterwarnings('ignore')

# Read configuration
config = configparser.ConfigParser()
config.read('config.cfg')

# Get configuration values
driver_path = config.get('Settings', 'driverpath')
username = config.get('Credentials', 'username')
password = config.get('Credentials', 'password')

# Initialize the ChromeDriver
driver = webdriver.Chrome()

# Navigate to LeetCode login page
driver.get("https://leetcode.com/accounts/github/login/?next=%2F")

# Wait for the 'Continue' button to be clickable and then click it
continue_button = WebDriverWait(driver, 10).until(
    EC.element_to_be_clickable((By.XPATH, "//button[contains(text(), 'Continue')]"))
)
continue_button.click()

# Fill in the GitHub login form
try:
    # Wait for the username field to be present
    username_field = WebDriverWait(driver, 10).until(
        EC.presence_of_element_located((By.ID, "login_field"))
    )
    password_field = driver.find_element(By.ID, "password")

    # Enter your GitHub username and password
    username_field.send_keys(username)
    password_field.send_keys(password)

    # Click the login button
    login_button = driver.find_element(By.NAME, "commit")
    login_button.click()
    print("Logged in successfully.")
except TimeoutException:
    print("Timeout while waiting for the login fields.")
    driver.quit()
    exit()

time.sleep(5)  # Adjust the time as needed

def parse_relative_time(time_string):
    units = {'minute': 60, 'hour': 3600, 'day': 86400, 'week': 604800, 'month': 2628000, 'year': 31536000}
    total_seconds = 0
    matches = re.findall(r'(\d+)\s+(minute|hour|day|week|month|year)s?', time_string)
    for amount, unit in matches:
        total_seconds += int(amount) * units[unit]
    return timedelta(seconds=total_seconds)

'''def get_most_recent_timestamp(file_path):
    if not os.path.exists(file_path):
        return None
    df = pd.read_csv(file_path)
    if df.empty:
        return None
    df['Finished Date'] = pd.to_datetime(df['Finished Date'])
    return df['Finished Date'].max()

submission_records_filename = 'leetcode_submissions.csv'
recent_datetime = get_most_recent_timestamp(submission_records_filename)'''
recent_datetime = None #duplcate using url
if recent_datetime is None:
    recent_datetime = datetime.now()

def scrape_page(url):
    driver.get(url)
    try:
        # Wait for the table body to be present
        WebDriverWait(driver, 5).until(
            EC.presence_of_element_located((By.XPATH, "//div[@id='submission-list-app']//table"))
        )
    except TimeoutException:
        print(f"Timeout waiting for page to load: {url}")
        return ""
    return driver.page_source

def collect_all_submissions(recent_datetime, existing_urls):
    page = 1
    all_data = []
    while True:
        url = f"https://leetcode.com/submissions/#/{page}"
        page_content = scrape_page(url)
        if not page_content:
            print(f"Empty page encountered: {url}")
            break
        # Parse the HTML content
        soup = BeautifulSoup(page_content, 'html.parser')
        table = soup.find('table', class_='table')
        if table:
            for row in table.find_all('tr')[1:]:  # Skip the header row
                cols = row.find_all('td')
                if len(cols) == 5:
                    time_submitted = cols[0].text.strip()
                    question_link = cols[1].find('a')
                    question = question_link.text.strip()
                    question_path = question_link['href']
                    status = cols[2].text.strip()
                    runtime = cols[3].text.strip()
                    language = cols[4].text.strip()
                    question_url = f"https://leetcode.com{question_path}"
                    # Check if the question URL already exists in the existing URLs
                    if question_url in existing_urls:
                        return all_data
                    # Convert relative time to absolute date
                    finished_date = (recent_datetime - parse_relative_time(time_submitted)).date()
                    all_data.append([finished_date, question, question_url, status, runtime, language])
            print(f"Successfully parsed page {page}")  # New printing statement
            # Check if "No more submissions." is present
            if "No more submissions." in page_content:
                print("Reached the end of submissions.")
                break
        page += 1
        time.sleep(5)  # Be respectful with rate limiting
    return all_data

def main():
    submission_records_filename = 'leetcode_submissions.csv'
    if os.path.exists(submission_records_filename):
        df_existing = pd.read_csv(submission_records_filename)
        existing_urls = set(df_existing['Question URL'])
    else:
        df_existing = pd.DataFrame()
        existing_urls = set()

    new_submissions = collect_all_submissions(recent_datetime, existing_urls)
    if new_submissions:
        df_new = pd.DataFrame(new_submissions, columns=['Finished Date', 'Question', 'Question URL', 'Status', 'Runtime', 'Language'])
        if not df_existing.empty:
            df_combined = pd.concat([df_new, df_existing]).drop_duplicates()
        else:
            df_combined = df_new
        df_combined.to_csv(submission_records_filename, index=False)
        print(f"Updated the CSV file with {len(new_submissions)} new submissions.")
        driver.quit()
    else:
        print("No new submissions found.")
        driver.quit()
    

if __name__ == "__main__":
    main()
    
