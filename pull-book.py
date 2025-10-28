import requests
import argparse

def pull_book(book_name, output_file):
    """
    Pull book data from Sefaria API and save to output_file.
    Returns True if successful, False otherwise.
    """
    if not validate_book_name(book_name):
        print(f"Book '{book_name}' not found in Sefaria.")
        return False
    url = f"https://www.sefaria.org/api/v3/texts/{book_name}"
    try:
        response = requests.get(url)
        response.raise_for_status()
        with open(output_file, 'w', encoding='utf-8') as f:
            f.write(response.text)
        print(f"Book '{book_name}' data saved to {output_file}.")
        return True
    except requests.RequestException as e:
        print(f"Error pulling book: {e}")
        return False


def validate_book_name(book_name):
    """
    Validate a book name using the Sefaria API.
    Returns True if the book exists, False otherwise.
    """
    url = f"https://www.sefaria.org/api/v2/raw/index/{book_name}"
    try:
        response = requests.get(url)
        if response.status_code == 200:
            return True
        elif response.status_code == 404:
            return False
        else:
            response.raise_for_status()
    except requests.RequestException:
        return False



def main():
    parser = argparse.ArgumentParser(description="Pull book data from API")
    parser.add_argument("--book_name", type=str, required=True, help="Name of the book to pull")
    parser.add_argument("--output_file", type=str, required=False, help="Output file to save the book data (defaults to <book_name>.json)")

    args = parser.parse_args()
    output_file = args.output_file if args.output_file else f"{args.book_name}.json"
    pull_book(args.book_name, output_file)



if __name__ == "__main__":
    main()