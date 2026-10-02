import requests

class ElementFetcher():
    """
    Simple integration of the SysMl v2 API.
    Via the project_id and a commit_id this class fetches all elements within this project 
    and returns the SysMl v2 json.
    """
    def __init__(self, project_id: str, commit_id: str, base_url: str = "http://sysml2.intercax.com:9000/"):
        self.project_id: str = project_id
        self.commit_id: str = commit_id
        self.base_url: str = base_url

        self.url: str = f"http://sysml2.intercax.com:9000/projects/{project_id}/commits/{commit_id}/elements"

        self.data = {}
        self.purged_data = {}

    def fetch(self) -> "ElementFetcher":
        print(f"Fetching: {self.url}")

        # Some arbitrary crazy high value to ensure that every element is loaded
        params = {"page[size]": 9999999} 
        response = requests.get(self.url, params=params)
        response.raise_for_status()
        self.data = response.json()

        return self
    
    def __clean_data(self, data):
        """
        Recursively remove:
        - keys whose value is None,
        - keys whose value is an empty list or empty dict,
        - items in lists that are None or become empty after cleaning.
        """
        if isinstance(data, dict):
            cleaned_dict = {}
            for k, v in data.items():
                cleaned_value = self.__clean_data(v)
                if cleaned_value is not None \
                and not (isinstance(cleaned_value, dict) and not cleaned_value) \
                and not (isinstance(cleaned_value, list) and not cleaned_value):
                    cleaned_dict[k] = cleaned_value
            return cleaned_dict

        elif isinstance(data, list):
            cleaned_list = []
            for item in data:
                cleaned_item = self.__clean_data(item)
                if cleaned_item is not None \
                and not (isinstance(cleaned_item, dict) and not cleaned_item) \
                and not (isinstance(cleaned_item, list) and not cleaned_item):
                    cleaned_list.append(cleaned_item)
            return cleaned_list

        else:
            return None if data is None else data


    def purge_empty_fields(self) -> "ElementFetcher":
        self.purged_data = self.__clean_data(self.data)
        return self

    def get_data(self) -> dict:
        return self.purged_data if self.purged_data else self.data