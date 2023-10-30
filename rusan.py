import requests
from bs4 import BeautifulSoup
from time import sleep
import pandas as pd

# This function fetches HTML from a webpage and makes a BeautifulSoup object from it.
def get_soup(base_url, subdirectory=""):
    try:
        response = requests.get(base_url + subdirectory) # Fetch HTML
        response.raise_for_status()
        return BeautifulSoup(response.text, "html.parser") # Return BeautifulSoup object from HTML
    except requests.exceptions.HTTPError as httperr:
        raise SystemExit(f"\nReceived status code [{response.status_code}]. Something is likely wrong with rusan.fo.\n{httperr}")
    except requests.exceptions.ConnectionError as conerr:
        raise SystemExit(f"\nCould not connect to rusan.fo. Check your internet connection or if rusan.fo is down.\n{conerr}")
    except requests.exceptions.RequestException as err:
        raise SystemExit(f"\nERROR! ERROR! An unexpected error occurred.\n{err}")

# This function finds all product categories (e.g. white wine, beer, vodka, etc.) and corresponding links.
def get_categories(soup):
    vertical_menu = soup.select_one(".VerticalMenu") # Find container containing categories
    categories_dict = {} # Define an empty dictionary to store categories and their links

    # Loop over main categories
    for main in vertical_menu.select(".Main"):
        # Find subcategories, if any (e.g., white wine is a subcategory of wine)
        category_code = main.get('data-categorycode')
        sub_container = vertical_menu.select_one(f'[data-categorycode="{category_code}"] + .SubContainer')
        
        # Find and store subcategories (except if it's beer, because beer subcategories are weird).
        # If there are no subcategories, use the main category name.
        # Subcategories are preferred, as it is desirable to differentiate between, for example, red wine, sparkling wine, and white wine.
        sub_categories = sub_container.select('.Sub') if sub_container and category_code != "OL" else [main]
        
        # Store category name and corresponding link
        for sub in sub_categories:
            category_name = sub.a.text
            url = sub.a['href']
            categories_dict[category_name] = url

    # Organic and Accessories categories are not relevant, so their links are deleted.
    # Technically, they should be deleted later, when filtering out non-alcoholic items, but doing it now saves rusan.fo from unnecessary requests later.
    for cat in ["Vistfrøði", "Tilhoyr"]:
        del categories_dict[cat]
    
    return categories_dict

# This function scrapes a single page on rusan. Part of the scrape_rusan function.
def scrape_page_data(wares_dict, soup, category):
    wares_dict["names"].extend(n.text for n in soup.select(".ItemTable>div>h3>a")) # Store product names
    wares_dict["volumes"].extend(v.text for v in soup.select(".InformationTable>.InformationRow>div:-soup-contains('litrar')")) # Store product volumes
    wares_dict["strengths"].extend(s.text for s in soup.select(".InformationTable>.InformationRow>div:-soup-contains('%')")) # Store product strengths
    wares_dict["prices"].extend(p.text for p in soup.select(".InformationRow.shop-cat-item-price>div:nth-of-type(2)")) # Store product prices
    n_products = len(soup.select(".ShopCategoryItemPictureList>.ItemTable")) # Find number of products on the page
    wares_dict["categories"].extend([category] * n_products) # Extend wares_dict["categories"] with the current category name, as many times as there are products on this page. Necessary for pandas.

# This function finds the link to the next page. Part of scrape_alcohol_data().
def get_next_page_url(soup):
            paging_el = soup.select_one("input[value='Næsta síða']") # Find "Next Page" button
            
            # Return the link to the next page, if it exists
            if paging_el:
                return paging_el["onclick"].split("'")[1]

# This function scrapes rusan and stores the data in a pandas dataframe
def scrape_rusan():
    rusan_url = "https://rusan.fo"
    # Define empty lists that will contain relevant data about the products
    wares = {
    "names": [],
    "volumes": [],
    "strengths": [],
    "prices": [],
    "categories": []
    }
    
    soup = get_soup(rusan_url, "/voeruskrá")
    categories_dict = get_categories(soup)

    # Loop over categories and their links
    for category, url in categories_dict.items():
        print(f"Scraping {category}")
        page_number = 1
        while True:
            print(f"\tpage {page_number}...", end="")
            soup = get_soup(rusan_url, url) # Fetch HTML for current category
            scrape_page_data(wares, soup, category)
            url = get_next_page_url(soup) # Fetch link to next page
            print(" done")
            page_number += 1
            sleep(0.5) # Wait for 1/2 second to not make too rapid requests
            
            # If there is no next page, move to the next category.
            if not url:
                print("\n")
                break
            
    # Return a dataframe with the data
    return pd.DataFrame({
        "name": wares["names"],
        "volume (liters)": wares["volumes"],
        "strength (%)": wares["strengths"],
        "price (dkk)": wares["prices"],
        "category": wares["categories"]
    })

# This function finds all products that are not alcohol-free
def get_alcoholic(df):
    return df[df["strength (%)"] > 0.5] # Find products with strength > 0.5%


# This function cleans and processes the data. It also filters out non-alcoholic products from the dataset.
def process_data(df):
    # Clean the data and change the format of the numbers so they can be used in calculations.
    df["volume (liters)"] = df["volume (liters)"].str.strip().str.split().str[0].str.replace(",", ".", regex=False).astype("float")
    df["strength (%)"] = df["strength (%)"].str.strip().str[:-1].str.replace(",", ".", regex=False).astype("float")
    df["price (dkk)"] = df["price (dkk)"].str.strip().str.replace(".", "", regex=False).str.replace(",", ".", regex=False).astype("float")
    
    # Filter out non-alcoholic products and return.
    return get_alcoholic(df)

# This function finds 6-packs, cases, and bundles and returns the size of the "bundles". Pertains to calc_alc_kr().
def get_bundle_quantities(df):
    bundle_regex = r"\(.*?([0-9]+).*\)" # Define regular expression that matches "bundles"
    # Find "bundles" and return their sizes
    bundles = df["name"].str.extract(bundle_regex, expand=False)
    
    return bundles.loc[bundles.notna()].astype("int")

# This function calculates alcohol per kr.
def calc_alc_kr(df):
    df["ml/kr (alcohol)"] = 10 * df["volume (liters)"] * df["strength (%)"] / df["price (dkk)"]  # Calculate alcohol/kr
    bundle_quantities = get_bundle_quantities(df)
    df.loc[bundle_quantities.index, "ml/kr (alcohol)"] *= bundle_quantities # Multiply alcohol/kr by their bundle size for bundles
    df["ml/kr (alcohol)"] = df["ml/kr (alcohol)"].round(2) # Round to 2 decimal places

# This function sorts the dataset by category and alcohol per kr.
def sort_data(df):
    return df.sort_values(["kategori", "ml/kr (alcohol)"], ascending=[True, False], ignore_index=True)

# This function writes to an Excel file.
def output_excel(df):
    while True:
        # Try to write to Excel
        try:
            df.to_excel("rusan.xlsx", index=False)
            print("Done! An Excel file has been placed in the directory.")
            break
        # If PermissionError is raised, ask if the user wants to try again
        except PermissionError:
            try_again = ""
            while try_again != "yes":
                try_again = input("Failed to write to Excel, because the rusan.xlsx file is in use. Try again? [yes/no]: ").lower()
                if try_again == "no":
                    raise SystemExit()
        # If any other exception besides PermissionError is raised, end the program.
        except Exception as err:
            raise SystemExit(f"Failed to write to Excel, due to an unexpected error.\n{err}")

# Main function
def main():
    alcohol_df = scrape_rusan()
    alcohol_df = process_data(alcohol_df)
    calc_alc_kr(alcohol_df)
    alcohol_df = sort_data(alcohol_df)
    output_excel(alcohol_df)
    
# Execute the main function
main()



