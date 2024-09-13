import requests
import podcastindex
from pprint import pprint
import argparse
from src.logger.logger_setup import logger

# Key: GA68D5DTDRRBWHDYZ57Z
# Secret: ZZTpQdc5br#dx3R$88p5$uQS9cHtzYkMWBMDpYee

config = {
    "api_key": "GA68D5DTDRRBWHDYZ57Z",
    "api_secret": "ZZTpQdc5br#dx3R$88p5$uQS9cHtzYkMWBMDpYee"
}


INSERT_QUERY = '''INSERT INTO (name, age) VALUES (?, ?)'''

index = podcastindex.init(config)


def search_podcasts(query):
    """
    Search for podcasts using a query string.

    Parameters:
    query (str): The query string to search for.

    Returns:
    list: A list of matching podcasts.
    """
    result = index.search(query)
    # pprint(result)
    return result

def download_file(url):
    """
    Download a file from a URL.

    Parameters:
    url (str): The URL of the file to download.

    Returns:
    str: The local filename of the downloaded file.
    """
    local_filename = url.split('/')[-1].split('?')[-2] + ".mp3"
    local_filename = "example.mp3"
    try:
        with requests.get(url, stream=True) as r:
            r.raise_for_status()
            with open(local_filename, 'wb') as f:
                for chunk in r.iter_content(chunk_size=8192): 
                    f.write(chunk)
    except Exception as e:
        logger.error(f"Error downloading file: {e}")
        return None
    return local_filename


def sort_podcasts_by_relevance(podcasts):
    """
    Sort a list of podcasts by relevance.

    Parameters:
    podcasts (list): A list of podcasts.

    Returns:
    list: A list of sorted podcasts.
    """
    return sorted(podcasts, key=lambda x: x['url'])

def write_to_db(title, url):
    import sqlite3

    # Connect to a database (or create one if it doesn't exist)
    conn = sqlite3.connect('podcast_index_urls.db')

    # Create a cursor object to interact with the database
    cursor = conn.cursor()

    # Create a table
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS podcast_urls (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        title TEXT NOT NULL,
        url TEXT NOT NULL,
        date_added DATE DEFAULT CURRENT_DATE
    )
    ''')

    cursor.execute('''
    INSERT INTO podcast_urls (title, url) VALUES (?, ?)
    ''', (title, url))

    # Commit the changes
    conn.commit()

    # Close the connection
    conn.close()


# podcastindex.org

# podcast_url="https://audioboom.com/posts/8496147-ep-491-who-piped-carl-winslow-feat-james-mccann-lemaire-lee-shawn-gardini.mp3?download=1"
# podcast_url="https://chrt.fm/track/9C8FAD/pdst.fm/e/rss.art19.com/episodes/ad8b4316-a1b2-4a08-8cfa-94f1e2cbf858.mp3?rss_browser=BAhJIg9BZ2dyaXZhdG9yBjoGRVQ%3D--5373ab09f7e0575889ee994727fc435324328290"
# podcast_url="https://www.podtrac.com/pts/redirect.mp3/pdst.fm/e/chrt.fm/track/7GB118/pfx.veritonicmetrics.com/quj9X/pscrb.fm/rss/p/mgln.ai/e/35/arttrk.com/p/ADCT2/traffic.megaphone.fm/ADV9688525577.mp3?updated=1714715847"
# download_file(podcast_url)
if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='Search for podcasts.')
    parser.add_argument('query', type=str, help='The search query')
    args = parser.parse_args()

    podcasts = search_podcasts(args.query)['feeds']
    pprint(sort_podcasts_by_relevance(podcasts))
    for podcast in podcasts:
        title = podcast['title']
        url = podcast['url']
        write_to_db(title, url)
        # download_file(url)
        break