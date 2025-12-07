"""
JustWatch Search - A Python script to search movies/series and view their streaming availability

Features:
1. Search for movies and TV series
2. View services/platforms where content is available, by country with audio/subtitle details
3. Filter results using regex patterns (country, audio, subtitles, etc.)
"""

import asyncio
import requests
import re
import sys
import argparse
from typing import List, Dict, Optional, Any
from dataclasses import dataclass, field
from enum import Enum


class MonetizationType(Enum):
    FLATRATE = "flatrate"  # Subscription
    BUY = "buy"
    RENT = "rent"
    FREE = "free"
    ADS = "ads"

@dataclass
class Offer:
    """Represents a streaming offer for a title"""
    country: str
    service_name: str
    service_id: int
    monetization_type: str
    presentation_type: str  # HD, SD, 4K, etc.
    price: Optional[str] = None
    currency: Optional[str] = None
    audio_languages: List[str] = field(default_factory=list[str])
    subtitle_languages: List[str] = field(default_factory=list[str])
    audio_technology: List[str] = field(default_factory=list[str])
    video_technology: List[str] = field(default_factory=list[str])
    url: Optional[str] = None

    def __str__(self) -> str:
        """String representation of the offer"""
        result = f"{self.country} - {self.service_name} ({self.monetization_type})"
        if self.price:
            result += f" - {self.price} {self.currency}"
        result += f" [{self.presentation_type}]"
        if self.audio_languages:
            result += f"\n  Audio: {', '.join(self.audio_languages)}"
        if self.subtitle_languages:
            result += f"\n  Subtitles: {', '.join(self.subtitle_languages)}"
        if self.audio_technology:
            result += f"\n  Audio Tech: {', '.join(self.audio_technology)}"
        if self.video_technology:
            result += f"\n  Video Tech: {', '.join(self.video_technology)}"
        return result

@dataclass
class Title:
    """Represents a movie or TV series"""
    title: str
    object_id: int
    node_id: str
    object_type: str
    release_year: Optional[int] = None
    imdb_id: Optional[str] = None
    tmdb_id: Optional[str] = None
    runtime: Optional[int] = None
    description: Optional[str] = None
    genres: List[str] = field(default_factory=list[str])
    production_countries: List[str] = field(default_factory=list[str])
    full_path: Optional[str] = None
    offers: Dict[str, List[Offer]] = field(default_factory=dict[str, List[Offer]])

    def __str__(self) -> str:
        """String representation of the title"""
        result = f"{self.title} ({self.release_year}) - {self.object_type}"
        if self.imdb_id:
            result += f" [IMDB: {self.imdb_id}]"
        if self.genres:
            result += f"\n  Genres: {', '.join(self.genres)}"
        if self.description:
            result += f"\n  {self.description[:200]}..."
        return result


class JustWatchFilter:
    """Class for filtering JustWatch offers using regex patterns"""
    
    def __init__(
        self,
        country_pattern: Optional[str] = None,
        service_pattern: Optional[str] = None,
        audio_pattern: Optional[str] = None,
        subtitle_pattern: Optional[str] = None,
        monetization_pattern: Optional[str] = None,
        presentation_pattern: Optional[str] = None
    ) -> None:
        self.country_pattern = country_pattern
        self.service_pattern = service_pattern
        self.audio_pattern = audio_pattern
        self.subtitle_pattern = subtitle_pattern
        self.monetization_pattern = monetization_pattern
        self.presentation_pattern = presentation_pattern

    def filter_offers(self, offers: Dict[str, List[Offer]]) -> Dict[str, List[Offer]]:
        """
        Filter offers using regex patterns
        
        Args:
            offers: Dictionary of offers to filter
            country_pattern: Regex pattern for country codes (e.g., "US|GB|CA")
            service_pattern: Regex pattern for service names (e.g., "Netflix|Disney")
            audio_pattern: Regex pattern for audio languages (e.g., "en|es")
            subtitle_pattern: Regex pattern for subtitle languages
            monetization_pattern: Regex pattern for monetization type (e.g., "flatrate|free")
            presentation_pattern: Regex pattern for presentation type (e.g., "4K|HD")
            
        Returns:
            Filtered dictionary of offers
        """
        filtered: Dict[str, List[Offer]] = {}
        for country, country_offers in offers.items():
            if self.country_pattern and not re.search(self.country_pattern, country, re.IGNORECASE):
                continue
            filtered_offers: List[Offer] = []
            for offer in country_offers:
                if self.service_pattern and not re.search(self.service_pattern, offer.service_name, re.IGNORECASE):
                    continue
                if self.monetization_pattern and not re.search(self.monetization_pattern, offer.monetization_type, re.IGNORECASE):
                    continue
                if self.presentation_pattern and not re.search(self.presentation_pattern, offer.presentation_type, re.IGNORECASE):
                    continue
                if self.audio_pattern:
                    audio_match = any(re.search(self.audio_pattern, lang, re.IGNORECASE) for lang in offer.audio_languages)
                    if not audio_match:
                        continue
                if self.subtitle_pattern:
                    subtitle_match = any(re.search(self.subtitle_pattern, lang, re.IGNORECASE) for lang in offer.subtitle_languages)
                    if not subtitle_match:
                        continue
                filtered_offers.append(offer)
            if filtered_offers:
                filtered[country] = filtered_offers
        return filtered


class JustWatchAPI:
    BASE_URL = "https://apis.justwatch.com"
    GRAPHQL_URL = f"{BASE_URL}/graphql"
    
    def __init__(self, proxy_url: str | None = None):
        self.use_proxy = True if proxy_url != None else False
        self.proxy_url = (proxy_url if proxy_url.endswith("/") else proxy_url + "/") if proxy_url else ""
        self.session = requests.Session()
        self.session.headers.update({
            'Content-Type': 'application/json',
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        })
    
    def _get_url(self, endpoint: str) -> str:
        if self.use_proxy and self.proxy_url:
            return f"{self.proxy_url}{self.BASE_URL}{endpoint}"
        return f"{self.BASE_URL}{endpoint}"
    
    def _graphql_request(self, query: str, variables: Dict[str, Any], operation_name: Optional[str] = None) -> Dict[str, Any]:
        """
        Make a GraphQL request to JustWatch API
        
        Args:
            query: GraphQL query string
            variables: Variables for the query
            operation_name: Optional operation name for the query
            
        Returns:
            Response data dictionary
        """
        url = self._get_url("/graphql")
        payload: Dict[str, Any] = {
            "query": query,
            "variables": variables
        }
        if operation_name:
            payload["operationName"] = operation_name
        try:
            response = self.session.post(url, json=payload)
            response.raise_for_status()
            data = response.json()
            if "errors" in data:
                print(f"GraphQL errors: {data['errors']}")
                raise Exception(f"GraphQL query failed: {data['errors']}")
            return data
        except requests.exceptions.RequestException as e:
            print(f"Error making request: {e}")
            if e.response is not None:
                print(f"Response: {e.response.text}")
            raise
    
    def search_titles(self, query: str, country: str = "US", max_results: int = 10) -> List[Title]:
        """
        Search for movies and TV series
        
        Args:
            query: Search query string
            country: Country code (e.g., "US", "GB", "DE")
            max_results: Maximum number of results to return
            
        Returns:
            List of Title objects
        """
        graphql_query = """
query GetSearchTitles(
  $searchTitlesFilter: TitleFilter!,
  $country: Country!,
  $language: Language!,
  $first: Int!,
  $formatPoster: ImageFormat,
  $profile: PosterProfile,
  $backdropProfile: BackdropProfile
) {
  popularTitles(
    country: $country
    filter: $searchTitlesFilter
    first: $first
    sortBy: POPULAR
    sortRandomSeed: 0
  ) {
    edges {
      ...SearchTitleGraphql
      __typename
    }
    __typename
  }
}

fragment SearchTitleGraphql on PopularTitlesEdge {
  node {
    id
    objectId
    objectType
    content(country: $country, language: $language) {
      title
      fullPath
      originalReleaseYear
      originalReleaseDate
      productionCountries
      runtime
      shortDescription
      genres {
        shortName
        __typename
      }
      externalIds {
        imdbId
        tmdbId
        __typename
      }
      posterUrl(profile: $profile, format: $formatPoster)
      backdrops(profile: $backdropProfile, format: $formatPoster) {
        backdropUrl
        __typename
      }
      __typename
    }
    __typename
  }
  __typename
}
"""
        variables: Dict[str, Any] = {
            "searchTitlesFilter": {
                "searchQuery": query,
                "includeTitlesWithoutUrl": True
            },
            "country": country,
            "language": "en",
            "first": max_results,
            "formatPoster": "JPG",
            "profile": "S718",
            "backdropProfile": "S1920"
        }
        result = self._graphql_request(graphql_query, variables, "GetSearchTitles")
        titles: List[Title] = []
        if "data" in result and "popularTitles" in result["data"]:
            for edge in result["data"]["popularTitles"]["edges"]:
                node = edge["node"]
                content = node.get("content", {})
                external_ids: Dict[str, str] = content.get("externalIds", {}) or {}
                title = Title(
                    title=content.get("title", "Unknown"),
                    object_id=node.get("objectId"),
                    node_id=node.get("id"),
                    object_type=node.get("objectType"),
                    release_year=content.get("originalReleaseYear"),
                    imdb_id=external_ids.get("imdbId"),
                    tmdb_id=external_ids.get("tmdbId"),
                    runtime=content.get("runtime"),
                    description=content.get("shortDescription"),
                    genres=[g["shortName"] for g in content.get("genres", []) if g],
                    production_countries=content.get("productionCountries", []),
                    full_path=content.get("fullPath")
                )
                titles.append(title)
        return titles
    
    def get_available_locales(self, full_path: str) -> List[str]:
        """
        Get available locales for a title
        
        Args:
            full_path: The full path of the title from JustWatch
            
        Returns:
            List of locale codes (e.g., ["en_US", "en_GB", "de_DE"])
        """
        try:
            url = f"{self.BASE_URL}/content/urls?path={full_path}"
            response = self.session.get(url)
            response.raise_for_status()
            data = response.json()
            href_lang_tags = data.get("href_lang_tags", [])
            return [tag["locale"] for tag in href_lang_tags if "locale" in tag]
        except Exception as e:
            print(f"Error getting locales: {e}")
            return []
    
    def get_offers(self, node_id: str, countries: List[str]) -> Dict[str, List[Offer]]:
        """
        Get streaming offers for a title across multiple countries
        
        Args:
            node_id: The node ID of the title
            countries: List of country codes
            
        Returns:
            Dictionary mapping country codes to lists of Offer objects
        """
        country_queries: List[str] = []
        for country in countries:
            country_queries.append(f"""
            {country.lower()}: offers(country: {country}, platform: $platform, filter: $filterBuy) {{
                ...TitleOffer
            }}
            """)
        graphql_query = f"""
query GetTitleOffers($nodeId: ID!, $language: Language!, $filterBuy: OfferFilter!, $platform: Platform! = WEB) {{
  node(id: $nodeId) {{
    ... on MovieOrShowOrSeasonOrEpisode {{
      {''.join(country_queries)}
    }}
  }}
}}

fragment TitleOffer on Offer {{
  id
  presentationType
  monetizationType
  retailPrice(language: $language)
  retailPriceValue
  currency
  type
  package {{
    id
    packageId
    clearName
    technicalName
    __typename
  }}
  standardWebURL
  subtitleLanguages
  videoTechnology
  audioTechnology
  audioLanguages
  __typename
}}
"""
        variables: Dict[str, Any] = {
            "nodeId": node_id,
            "language": "en",
            "filterBuy": {},
            "platform": "WEB"
        }
        result = self._graphql_request(graphql_query, variables, "GetTitleOffers")
        offers_by_country: Dict[str, List[Offer]] = {}
        if "data" in result and "node" in result["data"]:
            node = result["data"]["node"]
            for country in countries:
                country_key = country.lower()
                if country_key in node and node[country_key]:
                    offers: List[Offer] = []
                    for offer_data in node[country_key]:
                        package = offer_data.get("package", {})
                        offer = Offer(
                            country=country,
                            service_name=package.get("clearName", "Unknown"),
                            service_id=package.get("packageId", 0),
                            monetization_type=offer_data.get("monetizationType", "unknown"),
                            presentation_type=offer_data.get("presentationType", "SD"),
                            price=offer_data.get("retailPrice"),
                            currency=offer_data.get("currency"),
                            audio_languages=offer_data.get("audioLanguages", []),
                            subtitle_languages=offer_data.get("subtitleLanguages", []),
                            audio_technology=offer_data.get("audioTechnology", []),
                            video_technology=offer_data.get("videoTechnology", []),
                            url=offer_data.get("standardWebURL")
                        )
                        offers.append(offer)
                    offers_by_country[country] = offers
        return offers_by_country
    
    def get_all_offers(self, node_id: str, full_path: str) -> Dict[str, List[Offer]]:
        """
        Get all offers for a title across all available countries
        
        Args:
            node_id: The node ID of the title
            full_path: The full path of the title
            
        Returns:
            Dictionary mapping country codes to lists of Offer objects
        """
        locales = self.get_available_locales(full_path) if full_path != "" else []
        countries = list(set([locale.split("_")[-1] for locale in locales]))
        if not countries:
            countries = ["US", "GB", "DE", "FR", "ES", "IT", "CA", "AU"]
        return self.get_offers(node_id, countries)


class JustWatchSearch:
    """Main class for JustWatch search functionality with filtering"""

    def __init__(self, proxy_url: str | None = None):
        self.api = JustWatchAPI(proxy_url=proxy_url)

    def search(self, query: str, country: str = "US", max_results: int = 10, filter: Optional[JustWatchFilter] = None) -> List[Title]:
        """
        Search for movies and TV series
        
        Args:
            query: Search query string
            country: Country code for search context
            max_results: Maximum number of results
            
        Returns:
            List of Title objects
        """
        titles = self.api.search_titles(query, country, max_results)
        if not filter:
            return titles
        filtered_titles: List[Title] = []
        for title in titles:
            offers = self.get_offers(title)
            filtered_offers = filter.filter_offers(offers)
            if len(filtered_offers) == 0:
                continue
            filtered_titles.append(title)
            title.offers = filtered_offers
        return filtered_titles

    def get_offers(self, title: Title) -> Dict[str, List[Offer]]:
        """
        Get all streaming offers for a title
        
        Args:
            title: Title object to get offers for
            
        Returns:
            Dictionary mapping country codes to lists of offers
        """
        return self.api.get_all_offers(title.node_id, title.full_path if title.full_path else "")
    
    def print_offers(self, offers: Dict[str, List[Offer]], title: Optional[Title] = None):
        """
        Pretty print offers
        
        Args:
            offers: Dictionary of offers to print
            title: Optional title information to print
        """
        if title:
            print(f"\n{'='*80}")
            print(f"Streaming availability for: {title.title} ({title.release_year})")
            print(f"{'='*80}\n")
        if not offers:
            print("No offers found.")
            return
        total_offers = sum(len(country_offers) for country_offers in offers.values())
        print(f"Found {total_offers} offers across {len(offers)} countries:\n")
        for country in sorted(offers.keys()):
            print(f"\n{country} ({len(offers[country])} offers):")
            print("-" * 80)
            for offer in offers[country]:
                print(f"  {offer}\n")


async def main():
    parser = argparse.ArgumentParser(
        description='JustWatch Search - Search for movies/series and view availability',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Filter patterns (regex):
  Country:       -fc "US|GB|CA"          # Show offers only from US, GB, or CA
  Service:       -fs "Netflix|Disney.*"  # Netflix or Disney+
  Audio:         -fa "en|es"             # English or Spanish audio
                 -fa "sk|cs"             # Slovak or Czech audio
  Subtitles:     -ft "en"                # English subtitles available
  Monetization:  -fm "flatrate|free"     # Subscription or free
  Quality:       -fp "HD|4K"             # HD or 4K only
"""
    )
    
    parser.add_argument('-s', '--search', type=str, metavar='QUERY',
        help='Search query for movies/series'
    )
    parser.add_argument('-c', '--country', type=str, default='US', metavar='CODE',
        help='Country code for search context (default: US). Examples: US, GB, DE, FR, JP. Note: This sets which country\'s catalog to search in, not which offers to show. Use -fc to filter offers by country.'
    )
    parser.add_argument('-n', '--max-results', type=int, default=10, metavar='NUM',
        help='Maximum number of search results (default: 10)'
    )
    parser.add_argument('--show-offers', action='store_true',
        help='Show streaming offers for search results (interactive)'
    )
    parser.add_argument('--proxy-url', type=str, metavar='URL',
        help='Proxy URL to route requests through'
    )
    
    filter_group = parser.add_argument_group('filter options', 'Filter using regex patterns')
    filter_group.add_argument('-fc', '--filter-country', type=str, metavar='PATTERN',
        help='Filter offers by country code (regex). Example: "US|GB|DE"'
    )
    filter_group.add_argument('-fs', '--filter-service', type=str, metavar='PATTERN',
        help='Filter offers by service name (regex). Example: "Netflix|Disney.*"'
    )
    filter_group.add_argument('-fa', '--filter-audio', type=str, metavar='PATTERN',
        help='Filter offers by audio language (regex). Example: "en|es" or "sk|cs"'
    )
    filter_group.add_argument('-ft', '--filter-subtitle', type=str, metavar='PATTERN',
        help='Filter offers by subtitle language (regex). Example: "en"'
    )
    filter_group.add_argument('-fm', '--filter-monetization', type=str, metavar='PATTERN',
        help='Filter offers by monetization type (regex). Values: flatrate, buy, rent, free, ads'
    )
    filter_group.add_argument('-fp', '--filter-presentation', type=str, metavar='PATTERN',
        help='Filter offers by quality/presentation (regex). Values: SD, HD, 4K, etc.'
    )

    args = parser.parse_args()
    
    if len(sys.argv) == 1:
        parser.print_help()
        return
    
    if not args.search:
        print("Error: --search/-s is required")
        print("Run with -h for help")
        return
    
    jw = JustWatchSearch(args.proxy_url)
    jw_filter = JustWatchFilter(
        country_pattern=args.filter_country,
        service_pattern=args.filter_service,
        audio_pattern=args.filter_audio,
        subtitle_pattern=args.filter_subtitle,
        monetization_pattern=args.filter_monetization,
        presentation_pattern=args.filter_presentation
    )
    
    print(f"Searching for '{args.search}' in {args.country}...")
    titles = jw.search(args.search, country=args.country, max_results=args.max_results, filter=jw_filter)
    
    if not titles:
        print("No titles found.")
        return
    
    print(f"\nFound {len(titles)} results:\n")
    for i, title in enumerate(titles, 1):
        print(f"{i}. {title.title} ({title.release_year}) - {title.object_type}")
        if title.imdb_id:
            print(f"   IMDB: https://www.imdb.com/title/{title.imdb_id}")
        if title.tmdb_id:
            object_type_lower = title.object_type.lower().replace("show", "tv")
            print(f"   TMDB: https://www.themoviedb.org/{object_type_lower}/{title.tmdb_id}")
        if title.full_path:
            print(f"   JustWatch: https://justwatch.com{title.full_path}")
        if title.genres:
            print(f"   Genres: {', '.join(title.genres)}")
        if title.offers:
            total_offers = sum(len(country_offers) for country_offers in title.offers.values())
            print(f"   Offers available: {total_offers} (across {len(title.offers)} countries)")
        print()
    
    if args.show_offers:
        selected_title = titles[0]
        if len(titles) > 1:
            try:
                selection = input(f"Select a title (1-{len(titles)}) or 0 to cancel: ")
                selection = int(selection)
                if selection < 1 or selection > len(titles):
                    print("Cancelled.")
                    return
                selected_title = titles[selection - 1]
            except (ValueError, KeyboardInterrupt):
                print("\nCancelled.")
                return
        
        offers = selected_title.offers
        if not offers:
            print(f"\nFetching offers for '{selected_title.title}'...")
            offers = jw.get_offers(selected_title)
        
        if any([args.filter_country, args.filter_service, args.filter_audio,
                args.filter_subtitle, args.filter_monetization, args.filter_presentation]):
            print("Applying filters...")
            offers = jw_filter.filter_offers(offers)

        jw.print_offers(offers, selected_title)


if __name__ == "__main__":
    asyncio.run(main())
