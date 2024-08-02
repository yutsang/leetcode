import os, re, glob, time
import pandas as pd
from datetime import datetime, timedelta
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException
from bs4 import BeautifulSoup
from tqdm import tqdm
import textwrap
import configparser
import warnings
from time import sleep

warnings.filterwarnings('ignore')

def login(config):

    # Get configuration values
    driver_path = config.get('Settings', 'driverpath')
    username = config.get('Credentials', 'username')
    password = config.get('Credentials', 'password')

    # Initialize the ChromeDriver
    driver = webdriver.Chrome()
    
    

    # Navigate to LeetCode login page
    driver.get("https://leetcode.com/accounts/github/login/?next=%2F")
    
    time.sleep(2)

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
        time.sleep(20)
        #longer sleep time for new 2FA settings before clicking
        login_button.click()
        print("Check 2FA on Github App if applicable.")
        print("Logged in successfully.")
    except TimeoutException:
        print("Timeout while waiting for the login fields.")
        driver.quit()
        exit()
    return driver

def parse_relative_time(time_string):
    units = {'minute': 60, 'hour': 3600, 'day': 86400, 'week': 604800, 'month': 2628000, 'year': 31536000}
    total_seconds = 0
    matches = re.findall(r'(\d+)\s+(minute|hour|day|week|month|year)s?', time_string)
    for amount, unit in matches:
        total_seconds += int(amount) * units[unit]
    return timedelta(seconds=total_seconds)


recent_datetime = datetime.now()

def scrape_page(driver, url):
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

def collect_all_submissions(driver, recent_datetime, existing_urls):
    page = 1
    all_data = []
    while True:
        url = f"https://leetcode.com/submissions/#/{page}"
        page_content = scrape_page(driver, url)
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

def file_exists(title_slug):
    pattern = r'submissions/[1-9]\d{0,3}_' + re.escape(title_slug) + r'\.py'
    
    matching_files = glob.glob('submissions/*_' + title_slug + '.py')
    
    for file in matching_files:
        if re.match(pattern, file):
            return True
    
    return False

def get_question_number(title_slug):
    pattern = f"submissions/*_{title_slug}.py"
    matching_files = glob.glob(pattern)
    if matching_files:
        filename = os.path.basename(matching_files[0])
        match = re.match(r'(\d+)_', filename)
        if match:
            return match.group(1)
    return None

def question_counter(submission_records:pd.DataFrame, problems:pd.DataFrame)->int:
    total_count = int(len(problems))
    easy = int(len(submission_records[submission_records['Difficulty']=='Easy']))
    medium = int(len(submission_records[submission_records['Difficulty']=='Medium']))
    hard = int(len(submission_records[submission_records['Difficulty']=='Hard']))
    return total_count, easy, medium, hard
    

def extract_question_info(driver, url):
    question_number = None
    accepted_code = None
    submission_url = None
    
    try:
        # Extract question number
        time.sleep(2)
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
        time.sleep(3)
        accepted_submission = WebDriverWait(driver, 20).until(
            EC.presence_of_element_located((By.XPATH, "//div[@class='flex flex-col items-start']//div[@class='truncate text-green-s dark:text-dark-green-s']/span[text()='Accepted']"))
        )
        accepted_submission.click()
        
        # Wait for the page to load
        time.sleep(2)
        
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
    # Read configuration
    config = configparser.ConfigParser()
    config.read('config.cfg')
    submission_records_filename = config.get('Filenames', 'Control_file_path')
    
    if os.path.exists(submission_records_filename):
        df_existing = pd.read_csv(submission_records_filename)
        existing_urls = set(df_existing['Question URL'])
    else:
        df_existing = pd.DataFrame()
        existing_urls = set()
    
    driver = login(config)
    print("Parsing new submission records")
    new_submissions = collect_all_submissions(driver, recent_datetime, existing_urls)
    if new_submissions:
        df_new = pd.DataFrame(new_submissions, columns=['Finished Date', 'Question', 'Question URL', 'Status', 'Runtime', 'Language'])
        if not df_existing.empty:
            df_combined = pd.concat([df_new, df_existing]).drop_duplicates()
        else:
            df_combined = df_new.drop_duplicates()
        df_combined.to_csv(submission_records_filename, index=False)
        print(f"Updated the CSV file with {len(df_new.drop_duplicates())} new submissions.")
    else:
        print("No new submissions found.")
        
    ###############
    #submission handling
    ###############
    submission_records = pd.read_csv(submission_records_filename).sort_values(by=['Finished Date', 'Question'], ascending=[False, False])
    leetcode_problems = pd.read_csv('leetcode_problems.csv')

    submission_records = submission_records[submission_records['Status']=='Accepted'].drop_duplicates(subset='Question URL', keep='first')

    submission = pd.merge(submission_records, leetcode_problems, 
                     left_on='Question', right_on='Title', 
                     how='left').drop_duplicates(subset='Question')

    # Create submissions directory if it doesn't exist
    os.makedirs('submissions', exist_ok=True)

    count = 0
    for index, row in tqdm(submission.iterrows(), total=len(submission), desc="Processing submissions"):
    #for index, row in tqdm(submission.head(23).iterrows(), total=23, desc="Processing submissions"): #for testing
        #question_number = row.get('Question Number')
        title_slug = row['Title Slug']
        
        #if not question_number or not file_exists(question_number, title_slug):
        if not file_exists(title_slug):
            question_number, code, submission_url = extract_question_info(driver, row['Question URL'])
            sleep(2)  # Be respectful with rate limiting
            
            if question_number and code:
                file_name = f"submissions/{question_number}_{title_slug}.py"
                
                with open(file_name, 'w') as f:
                    f.write(code)
                #print(f"Created file: {file_name}")
                count+=1
                
                # Update the DataFrame
                submission.at[index, 'Question Number'] = int(question_number)
                submission.at[index, 'Submission Url'] = submission_url

            else:
                tqdm.write(f"Failed to extract information for: {row['Question URL']}")
                
        #else:
            #tqdm.write(f"File already exists for question: {title_slug}")
        
    if count > 0: print(f'Created {count} .py file(s).')
    else: print("All .py files have already created!")

    # Close the browser
    driver.quit()
    
    print("Creating Markdown Files!")
    # Define the format for the markdown table
    # Initialize the markdown table
    time = datetime.now()
    total_problems, easy, medium, hard = question_counter(submission, leetcode_problems)
    markdown_format = '''
# Leetcode Study Log with Python Auto created by [autoleetcode](https://github.com/yutsang/leetcode)
Update time:  {time_display}

Progress: **{total_finished} / {problems}** problems (Easy: {easy_no}, Medium: {medium_no}, Hard: {hard_no})

For tool handbook, please follow this [Usage Guide](https://github.com/yutsang/leetcode/blob/main/autoleetcode.md).  
For any bugs, please give me an [issue](https://github.com/yutsang/leetcode/issues).

| Question # | Finished Date | Title | Submission | Difficulty |
|:---:|:---:|:---:|:---:|:---:|
'''.format(
        time_display = time.strftime('%Y-%m-%d %H:%M:%S'),
        total_finished = easy + medium + hard,
        problems = total_problems,
        easy_no = easy,
        medium_no = medium,
        hard_no = hard,
    )

    # Add rows to the markdown table
    for index, row in submission.iterrows():
        question_number = get_question_number(row['Title Slug'])
        if question_number:  # Ensure question_number is not None
            markdown_format += f"|{question_number}|{row['Finished Date']}|[{row['Question']}]({row['Question URL']}/description/)|[Python](https://github.com/yutsang/leetcode/blob/main/submissions/{question_number}_{row['Title Slug']}.py)|{row['Difficulty']}|\n"
        else:
            print(f"Warning: No matching file found for title slug '{row['Title Slug']}'")
        
    # Save to a markdown file
    with open('README.md', 'w') as file:
        file.write(markdown_format)

    print("Markdown file generated successfully.")
    
if __name__ == "__main__":
    main()
    
