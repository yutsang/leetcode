import time
import pandas as pd
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

def collect_all_submissions():
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
                    all_data.append([time_submitted, question, f"https://leetcode.com{question_path}", status, runtime, language])
        
        print(f"Successfully parsed page {page}")  # New printing statement
        
        # Check if "No more submissions." is present
        if "No more submissions." in page_content:
            print("Reached the end of submissions.")
            break
        
        page += 1
        time.sleep(2)  # Be respectful with rate limiting
    
    # Create a DataFrame and save to CSV
    df = pd.DataFrame(all_data, columns=['Time Submitted', 'Question', 'Question URL', 'Status', 'Runtime', 'Language'])
    df.to_csv('leetcode_submissions.csv', index=False)
    print("Saved all submissions to leetcode_submissions.csv")

# Collect all submissions
collect_all_submissions()

# Close the browser
driver.quit()
