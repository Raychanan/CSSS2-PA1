"""
CAPP 30122: Course Search Engine Part 1

Your name: Rui Chen
"""
# DO NOT REMOVE THESE LINES OF CODE
# pylint: disable-msg=invalid-name, redefined-outer-name, unused-argument, unused-variable

from collections import deque, defaultdict
import json
import sys
import re
import bs4
import util
import unicodedata

INDEX_IGNORE = set(['a', 'also', 'an', 'and', 'are', 'as', 'at', 'be',
                    'but', 'by', 'course', 'for', 'from', 'how', 'i',
                    'ii', 'iii', 'in', 'include', 'is', 'not', 'of',
                    'on', 'or', 's', 'sequence', 'so', 'social', 'students',
                    'such', 'that', 'the', 'their', 'this', 'through', 'to',
                    'topics', 'units', 'we', 'were', 'which', 'will', 'with',
                    'yet'])

def request_and_parse_page(url):
    """
    Request and parse a page.
    Input:
        url: a string of a URL.
    Returns:
        soup: parsed HTML soup.
        redirected_url.
    """
    request_object = util.get_request(url)
    # If not `None`, the reqeust is successful.
    if not request_object and request_object.status_code != 200:
        return
    request_text = util.read_request(request_object)
    if not request_text:
        return
    soup = bs4.BeautifulSoup(request_text, "html5lib")
    # If soup does not have any `a` tag, return.
    if not soup.find_all("a"):
        return
    return soup, util.get_request_url(request_object)


def get_complete_url(parent_url, suburl):
    """
    Return the complete url of the given url. If it’s not an absolute url by
    using `util.is_absolute_url()`, first keep only the part of the URL before,
    that is, remove fragment (`util.remove_fragment(url)`)  and then convert it
    to an absolute url with `util.convert_if_relative_url(url1, url2)`. 
    
    Input:
        parent_url: a string of a URL.
        suburl: a string of a URL. Might be relative.
    Returns:
        complete_url: a string of a URL.
    """

    if not util.is_absolute_url(suburl):
        sublink = util.remove_fragment(suburl)
        sublink = util.convert_if_relative_url(parent_url, sublink)
        return sublink
    else:
        return suburl


def find_links(soup, parent_url):
    """
    Given a soup, return a list of complete URLs in the page.
    
    Input:
        soup: a parsed HTML soup.
        parent_url: a string of a URL.
    Returns:
        links: a list of complete URLs.
    """
    
    external_links = []
    a_tags = soup.find_all("a")
    for a_tag in a_tags:
        sublink = a_tag.get("href")
        complete_sublink = get_complete_url(parent_url, sublink)
        if complete_sublink is None:
            continue
        external_links.append(complete_sublink)
    return external_links


def filter_link(links, limiting_domain, visited_queue, to_be_crawled_queue):
    """
    Given a link, return True if it is a link to a course page.

    Input:
        links: a list of complete URLs.
        limiting_domain: a string of a domain name.
        visited_queue: a deque of urls.
        to_be_crawled_queue: a deque of urls.
    Returns:
        filtered_links: a list of complete URLs.
    """

    filtered_links = []
    for external_link in links:
        if not util.is_url_ok_to_follow(external_link, limiting_domain):
            continue
        # Change from https to http.
        http_external_link = re.sub(r"https", "http", external_link)
        if (
            http_external_link not in visited_queue
            and http_external_link not in to_be_crawled_queue
            and external_link not in to_be_crawled_queue
            and external_link not in visited_queue
        ):
            filtered_links.append(external_link)
    return filtered_links


def split_course_code(course_code):
    """
    If hyphen is in the course code, create separate course codes for each part.
    For example, ARTV 22000-22002 will be split into ARTV 22000 and ARTV 22002.
    Otherwise, return the original course code.

    Input:
        course_code: a string of a course code.
    Returns:
        course_code_list: a list of course codes.
    """

    if "-" in course_code:
        course_dept = course_code.split()[0]
        course_digit_list = course_code.split()[1].split("-")
        # Concatenate course codes.
        course_code_list = [
            course_dept + " " + course_digit for course_digit in course_digit_list
        ]
    else:
        course_code_list = [course_code]
    return course_code_list


def block_text_to_words(title_block_text, desc_block_text):
    """
     From texts under title and description to filtered matched words.

    Args:
        title_block_text (str): a string of a block text.
        desc_block_text (str): a string of a block text.

    Returns:
        list: a list of filtered matched words.
    """
    
    # Merge title text and desc text into one string. And lowercase it.
    lookup_str = title_block_text + " " + desc_block_text
    lookup_str = lookup_str.lower()

    all_words = lookup_str.split()
    # Strip trailing punctuation.
    all_words = [word.rstrip(".,;:") for word in all_words]
    word_pattern = re.compile(r"^[a-zA-Z][a-zA-Z0-9_]*$")
    matched_words = [word for word in all_words if word_pattern.match(word)]

    filtered_matched_words = [
        word for word in matched_words if word not in INDEX_IGNORE
    ]

    return filtered_matched_words


def extract_title_and_desc(div_tag):
    """
    Extract title and description from a div tag.

    Returns:
        str: a string of a title block text.
        str: a string of a description block text.
    """

    title_block_text = div_tag.find("p", class_="courseblocktitle").text
    title_block_text = unicodedata.normalize("NFKD", title_block_text)
    desc_block_text = div_tag.find("p", class_="courseblockdesc").text
    return title_block_text, desc_block_text


def extract_course_code_and_id(title_block_text, course_map):
    """
    Extract course code from a title block text. Also extract course id.

    Args:
        title_block_text (str): a string of a title block text.
        course_map (dict): a dictionary of course codes and course ids.

    Returns:
        list: a list of course codes.
        list: a list of course ids.
    """

    course_code = title_block_text.split(".")[0]
    course_code_list = split_course_code(course_code)
    course_id_list = [course_map[course_code] for course_code in course_code_list]
    return course_code_list, course_id_list


def scrape_course_content(soup, course_map):
    """
    Scrape courses and clean words under each course. Assign all words to the
    course id. 

    Returns:
        dict: a dictionary of course ids and words.
    """
    
    div_tags = soup.find_all("div", class_="courseblock")

    page_course_id_words_dict = {}
    for div_tag in div_tags:
        title_block_text, desc_block_text = extract_title_and_desc(div_tag)
        course_code_list, course_id_list = extract_course_code_and_id(
            title_block_text, course_map
        )
        filtered_matched_words = block_text_to_words(title_block_text, desc_block_text)

        # Add all filtered matched words to course id dict.
        for course_id in course_id_list:
            if course_id not in page_course_id_words_dict:
                page_course_id_words_dict[course_id] = set(filtered_matched_words)
            else:
                page_course_id_words_dict[course_id].update(filtered_matched_words)
    return page_course_id_words_dict


def add_page_content_to_final_dict(page_course_id_words_dict, result):
    """
    Append content of a page to the final result.

    Args:
        page_course_id_words_dict (dict): a dictionary of course ids and words.
        result (dict): a dictionary of course ids and words.

    Returns:
        dict: a dictionary of course ids and words.
    """

    if not page_course_id_words_dict:
        return result
    for course_id, words in page_course_id_words_dict.items():
        if course_id not in result:
            result[course_id] = set(words)
        else:
            result[course_id].update(words)
    return result


def go(num_pages_to_crawl, course_map_filename, index_filename):
    """
    Crawl the college catalog and generates a CSV file with an index.

    Inputs:
        num_pages_to_crawl: the number of pages to process during the crawl
        course_map_filename: the name of a JSON file that contains the mapping
          course codes to course identifiers
        index_filename: the name for the CSV of the index.

    Outputs:
        CSV file of the index index.
    """

    starting_url = (
        "http://www.classes.cs.uchicago.edu/archive/2015/winter"
        "/12200-1/new.collegecatalog.uchicago.edu/index.html"
    )
    limiting_domain = "classes.cs.uchicago.edu"

    with open(course_map_filename, "r") as f:
        course_map = json.load(f)
        
    
    # Set up two queues, one for urls to visit, one for urls that have been.
    to_be_crawled_queue = deque()
    to_be_crawled_queue.append(starting_url)
    visited_queue = deque()

    result = defaultdict(set)
    while len(visited_queue) < num_pages_to_crawl and len(to_be_crawled_queue) > 0:
        link = to_be_crawled_queue.popleft()
        print("now scraping link:", link)
        soup, real_link = request_and_parse_page(link)
        visited_queue.append(link)
        if not soup:
            continue
        # Find and process all links on the page.
        external_complete_links = find_links(soup, real_link)
        filtered_links = filter_link(
            external_complete_links, limiting_domain, visited_queue, to_be_crawled_queue
        )
        to_be_crawled_queue.extend(filtered_links)
        # Scrape course info.
        page_course_info_dict = scrape_course_content(soup, course_map)
        if not page_course_info_dict:
            continue
        # Add page content to final result.
        result = add_page_content_to_final_dict(page_course_info_dict, result)
        
    # Output to file.
    with open(index_filename, "w") as f:
        for course_id, words in result.items():
            for word in words:
                f.write("{}|{}\n".format(course_id, word))

    return result, visited_queue


if __name__ == "__main__":
    usage = "python3 crawl.py <number of pages to crawl>"
    args_len = len(sys.argv)
    course_map_filename = "course_map.json"
    index_filename = "catalog_index.csv"
    if args_len == 1:
        num_pages_to_crawl = 1000
    elif args_len == 2:
        try:
            num_pages_to_crawl = int(sys.argv[1])
        except ValueError:
            print(usage)
            sys.exit(0)
    else:
        print(usage)
        sys.exit(0)

    go(num_pages_to_crawl, course_map_filename, index_filename)
