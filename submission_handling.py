import pandas as pd
import re
from datetime import datetime, timedelta

import pandas as pd 

submission_records_filename = 'leetcode_submissions.csv'
submission_records = pd.read_csv(submission_records_filename)
leetcode_problems = pd.read_csv('leetcode_problems.csv')
#leetcode_problems['Question Number'] = leetcode_problems.reset_index().index + 1

# Function to parse relative time strings
def parse_relative_time(time_string):
    units = {'minute': 60, 'hour': 3600, 'day': 86400, 'week': 604800, 'month': 2628000, 'year': 31536000}
    total_seconds = 0
    matches = re.findall(r'(\d+)\s+(minute|hour|day|week|month|year)s?', time_string)
    for amount, unit in matches:
        total_seconds += int(amount) * units[unit]
    return timedelta(seconds=total_seconds)

# Get the most recent timestamp from file creation or modification date
def get_most_recent_timestamp(file_path):
    import os
    creation_time = os.path.getctime(file_path)
    modification_time = os.path.getmtime(file_path)
    return datetime.fromtimestamp(max(creation_time, modification_time))

recent_datetime = get_most_recent_timestamp(submission_records_filename)

submission_records.insert(1,'Finished Date', 0)
submission_records['Finished Date'] = submission_records['Time Submitted'].apply(lambda x: (recent_datetime - parse_relative_time(x)).date())
submission_records = submission_records.drop(columns='Time Submitted').sort_values(by='Finished Date', ascending=False)

submission_records = submission_records[submission_records['Status']=='Accepted'].drop_duplicates(subset='Question URL', keep='first')

submission = pd.merge(submission_records, leetcode_problems, 
                     left_on='Question', right_on='Title', 
                     how='left').drop_duplicates(subset='Question')#.drop(columns=['Title', 'Status'])#.rename(columns={'index':'Question Number'})
#coz only status = 'Accepted' woould be kept

#####################
import os
import time
import pandas as pd
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException
import configparser
from bs4 import BeautifulSoup
import re

# Read configuration
config = configparser.ConfigParser()
config.read('config.cfg')

# Get configuration values
driver_path = config.get('Settings', 'driverpath')
username = config.get('Credentials', 'username')
password = config.get('Credentials', 'password')

# Create submissions directory if it doesn't exist
os.makedirs('submissions', exist_ok=True)

def file_exists(question_number, title_slug):
    return os.path.exists(f"submissions/{question_number}_{title_slug}.py")

def extract_question_info(driver, url):
    question_number = None
    accepted_code = None
    submission_url = None
    
    try:
        # Extract question number
        time.sleep(5)
        driver.get(url)
        title_element = WebDriverWait(driver, 20).until(
            EC.presence_of_element_located((By.XPATH, "//a[contains(@class, 'no-underline') and contains(@class, 'hover:text-blue-s')]"))
        )
        title_text = title_element.text
        match = re.search(r'^(\d+)', title_text)
        if match:
            question_number = match.group(1)
        
        # Navigate to submissions page
        submissions_url = url + "/submissions/"
        driver.get(submissions_url)
        
        # Find the first 'Accepted' submission
        time.sleep(5)
        accepted_submission = WebDriverWait(driver, 20).until(
            EC.presence_of_element_located((By.XPATH, "//div[@class='flex flex-col items-start']//div[@class='truncate text-green-s dark:text-dark-green-s']/span[text()='Accepted']"))
        )
        accepted_submission.click()
        
        # Wait for the page to load
        time.sleep(5)
        
        # Get the current URL of the submission
        submission_url = driver.current_url
        
        # Scroll to the bottom of the page to trigger any lazy-loading
        driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
        time.sleep(2)  # Wait for content to load after scrolling
        
        # Get the full HTML using JavaScript
        full_html = driver.execute_script("return document.documentElement.outerHTML;")
        
        # Parse the HTML content with BeautifulSoup
        soup = BeautifulSoup(full_html, 'html.parser')

        # Find the code element with the class 'language-python'
        code_element = soup.find('code', class_='language-python')

        if code_element:
            # Extract the text content from all nested spans
            accepted_code = ''.join(span.get_text() for span in code_element.find_all('span', recursive=False))
        
    except TimeoutException:
        print(f"Timeout waiting for page to load: {url}")
    except NoSuchElementException:
        print(f"Required element not found at: {url}")
    except Exception as e:
        print(f"An error occurred: {str(e)}")
    
    return question_number, accepted_code, submission_url

def main():
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
    
    PATH = 'submissions'
    if not os.path.exists(PATH):
        os.makedirs(PATH)

    # Assuming 'submission' is your DataFrame
    for index, row in submission.head(10).iterrows():
        question_number = row.get('Question Number')
        title_slug = row['Title Slug']
        
        if not question_number or not file_exists(question_number, title_slug):
            question_number, code, submission_url = extract_question_info(driver, row['Question URL'])
            
            if question_number and code:
                file_name = f"submissions/{question_number}_{title_slug}.py"
                
                with open(file_name, 'w') as f:
                    f.write(code)
                print(f"Created file: {file_name}")
                
                # Update the DataFrame
                submission.at[index, 'Question Number'] = question_number
                submission.at[index, 'Submission Url'] = submission_url
            else:
                print(f"Failed to extract information for: {row['Question URL']}")
        else:
            print(f"File already exists for question {question_number}: {title_slug}")
        
        time.sleep(2)  # Be respectful with rate limiting

    
    # Display the updated DataFrame
    submission.head(5)
    # Close the browser
    driver.quit()

if __name__ == "__main__":
    main()
    
# Define the format for the markdown table
markdown_format = """
| Question # | Finished Date | Title | Submission | Difficulty |
|:---:|:---:|:---:|:---:|:---:|
"""

# Add rows to the markdown table
for index, row in submission.iterrows():
    markdown_format += f"|{row['Question Number']}|{row['Finished Date']}|[{row['Question']}]({row['Question URL']+'/description/'})|<a href='https://github.com/yutsang/leetcode/blob/main/submissions/{row['Question Number']}_{row['Title Slug']}.py'>Python</a>|{row['Difficulty']}|\n"

# Save to a markdown file
with open('README.md', 'w') as file:
    file.write(markdown_format)

print("Markdown file generated successfully.")