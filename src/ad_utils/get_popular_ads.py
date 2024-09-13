import requests
from bs4 import BeautifulSoup
from selenium.webdriver.firefox.options import Options
from selenium import webdriver
from src.logger.logger_setup import logger

# Set up Firefox options
options = Options()
options.headless = True

# Create a new instance of the Firefox driver with the headless option

def get_popular_ads():
    driver = webdriver.Firefox(options=options)
# Go to the webpage
    try:
        driver.get('https://www.podchaser.com/brands')
    except Exception as e:
        logger.error(f"Failed to load webpage: {e}")
        driver.quit()
        exit(1)

    # Get the HTML content of the webpage
    html = driver.page_source

    # Parse the HTML content with BeautifulSoup
    soup = BeautifulSoup(html, 'html.parser')
    buttons = soup.find_all('button', {'class': '_14bpxty', 'data-testid': 'listItemButton'})

    if not buttons:
        logger.info("No ads found")
        driver.quit()
        exit(0)

    # Now you can use `soup` to navigate and search the HTML document
    with open('popular_ads.txt', 'a') as file:
        for button in buttons:
            try:
                company = button.find('p', {'class':'_c7p45a'}).text
                file.write(company + '\n')
            except AttributeError:
                logger.error("Failed to find company name")

    # Close the browser
    driver.quit()


if __name__ == '__main__':
    get_popular_ads()