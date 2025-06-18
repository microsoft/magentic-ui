from typing import Dict, List, Literal
import tldextract
from urllib.parse import urlparse

URL_ALLOWED: Literal["allowed"] = "allowed"
URL_REJECTED: Literal["rejected"] = "rejected"

UrlStatus = Literal["allowed", "rejected"]


class UrlStatusManager:
    """
    A class to manage URL access control through allow/reject lists and explicit blocking.

    The URL matching is hierarchical and follows these rules:
    1. Block list is checked first - if URL matches any blocked pattern, access is denied
    2. For remaining URLs, if no status list is defined (None), all URLs are allowed
    3. Otherwise, URL must explicitly match an allowed pattern and not match any rejected patterns

    Note:
        Overlapping URLs with different statuses will result in undefined behavior.
        Example: { "example.com": "allowed", "example.com/foo": "rejected" }
    """

    url_statuses: Dict[str, UrlStatus] | None
    # TODO: There's a lot of logic around url_statuses being None. Use a separate list to check if a url is explicitly blocked
    url_block_list: List[str] | None

    def __init__(
        self,
        url_statuses: Dict[str, UrlStatus] | None = None,
        url_block_list: List[str] | None = None,
    ) -> None:
        """
        Args:
            url_statuses (Dict[str, UrlStatus], optional): initial url status settings. All urls are valid if None. Default: None.
            url_block_list (List[str], optional): initial url block list. Default: None.
        """
        self.url_statuses = None
        # a little bit of a hack to make sure there are no trailing slashes, since they mess with the comparison later on
        if url_statuses is not None:
            self.url_statuses = {
                key.rstrip("/"): value for key, value in url_statuses.items()
            }

        self.url_block_list = url_block_list

    def set_url_status(self, url: str, status: UrlStatus) -> None:
        """
        Adds a website to the manager. No-op if initialization parameter was None

        Args:
            url (str): The website to add.
            status (UrlStatus): The status of the url. Can be either "allowed" or "rejected".
        """
        if self.url_statuses is not None:
            url = url.strip()
            # Trailing slash messes up the comparison later on
            url = url.rstrip("/")
            self.url_statuses[url] = status

    def _is_url_match(self, registered_url: str, proposed_url: str) -> bool:
        """
        Checks if a proposed URL matches a registered URL pattern.

        Args:
            registered_url (str): The registered URL pattern to match against.
            proposed_url (str): The proposed URL to check.

        Returns:
            bool: True if the proposed URL matches the registered URL pattern, False otherwise.
        """
        # If no scheme is provided, assume http
        if not urlparse(registered_url).scheme:
            registered_url = "http://" + registered_url
        if not urlparse(proposed_url).scheme:
            proposed_url = "http://" + proposed_url

        parsed_registered_url = urlparse(registered_url)
        parsed_proposed_url = urlparse(proposed_url)
        extracted_registered_url = tldextract.extract(registered_url)
        extracted_proposed_url = tldextract.extract(proposed_url)

        # if both urls have a scheme, check if they are the same (http and https are treated as the same)
        http_equivalent_schemes = ["http", "https"]
        if (
            parsed_registered_url.scheme in http_equivalent_schemes
            and parsed_proposed_url.scheme in http_equivalent_schemes
        ):
            pass
        elif parsed_registered_url.scheme != parsed_proposed_url.scheme:
            return False

        # Check each component of the URL
        # TODO: what to do about params, query, and fragment components?
        if extracted_registered_url.subdomain:
            if extracted_registered_url.subdomain != extracted_proposed_url.subdomain:
                return False
        if extracted_registered_url.domain != extracted_proposed_url.domain:
            return False
        if (
            extracted_registered_url.suffix
            and extracted_proposed_url.suffix != extracted_registered_url.suffix
        ):
            return False
        if parsed_registered_url.path:
            if not parsed_proposed_url.path.startswith(parsed_registered_url.path):
                return False

        return True

    def is_url_blocked(self, url: str) -> bool:
        """
        Checks if a url is explicitly blocked.

        Args:
            url (str): The website to check.

        Returns:
            bool: True if the url is blocked, False otherwise.
        """
        if self.url_block_list is None:
            return False
        if any(self._is_url_match(site, url) for site in self.url_block_list):
            return True
        return False

    def is_url_rejected(self, url: str) -> bool:
        """
        Checks if the user explicitly rejected approval of a url. This function does NOT check against the allowed list.

        Args:
            url (str): The website to check.

        Returns:
            bool: True if the url was rejected by the user, False otherwise.
        """
        if self.is_url_blocked(url):
            return True
        if self.url_statuses is None:
            return False
        if any(
            self._is_url_match(site, url) and self.url_statuses[site] == URL_REJECTED
            for site in self.url_statuses
        ):
            return True
        return False

    def is_url_allowed(self, url: str) -> bool:
        """
        Checks if a website is allowed. This function does NOT check against the rejected list

        Args:
            url (str): The website to check.

        Returns:
            bool: True if the url is allowed, False otherwise.
        """
        if self.is_url_blocked(url):
            return False
        if self.url_statuses is None:
            return True
        if not any(
            self._is_url_match(site, url) and self.url_statuses[site] == URL_ALLOWED
            for site in self.url_statuses
        ):
            return False
        return True

    def get_allowed_sites(self) -> List[str] | None:
        """
        Returns a list of all allowed sites.

        Returns:
            List[str] | None: A list of all allowed sites. None if all sites are allowed.
        """
        if not self.url_statuses:
            return None
        return [
            site for site in self.url_statuses if self.url_statuses[site] == URL_ALLOWED
        ]

    def get_rejected_sites(self) -> List[str] | None:
        """
        Returns a list of all rejected sites.
        Returns:
            List[str] | None: A list of all rejected sites. None if all sites are allowed.
        """
        if not self.url_statuses:
            return None
        return [
            site
            for site in self.url_statuses
            if self.url_statuses[site] == URL_REJECTED
        ]

    def get_blocked_sites(self) -> List[str] | None:
        """
        Returns a list of all blocked sites.
        Returns:
            List[str] | None: A list of all blocked sites. None if there are no blocked sites.
        """
        return self.url_block_list
