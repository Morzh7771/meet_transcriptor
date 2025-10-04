import requests
import time
import re
import logging
import os
from dotenv import load_dotenv
from dataclasses import dataclass
from typing import List, Dict, Optional
from bs4 import BeautifulSoup, XMLParsedAsHTMLWarning
import warnings
import sys

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.backend.vector_db.qdrant_manager_law import QdrantManager

warnings.filterwarnings("ignore", category=XMLParsedAsHTMLWarning)
load_dotenv()
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

@dataclass
class BillInfo:
    congress: int
    bill_type: str
    bill_number: str
    title: str
    enacted_date: Optional[str] = None
    law_number: Optional[str] = None

class CongressAPIClient:
    def __init__(self, api_key: str):
        self.api_key = api_key
        self.base_url = "https://api.congress.gov/v3"
        self.session = requests.Session()
        self.session.headers.update({'X-API-Key': api_key, 'Content-Type': 'application/json'})
        
    def _make_request(self, endpoint: str, params: Dict = None) -> Dict:
        url = f"{self.base_url}/{endpoint.lstrip('/')}"
        if params is None:
            params = {}
        params['format'] = 'json'
        
        try:
            time.sleep(0.2)
            response = self.session.get(url, params=params, timeout=30)
            response.raise_for_status()
            return response.json()
        except requests.RequestException as e:
            logger.error(f"API request failed: {e}")
            return {}
    
    def get_enacted_bills(self, congress_numbers: List[int], limit: int = 250) -> List[Dict]:
        all_bills = []
        for congress in congress_numbers:
            logger.info(f"Fetching bills from {congress}th Congress...")
            
            for bill_type in ['hr', 's', 'hjres', 'sjres']:
                offset = 0
                while True:
                    data = self._make_request(f"bill/{congress}/{bill_type}", 
                                            {'limit': min(limit, 250), 'offset': offset})
                    
                    if 'bills' not in data or not data['bills']:
                        break
                    
                    bills = data['bills']
                    enacted_bills = [bill for bill in bills if self._is_bill_enacted(bill)]
                    
                    if enacted_bills:
                        logger.info(f"Found {len(enacted_bills)} enacted {bill_type} bills in {congress}th Congress")
                        all_bills.extend(enacted_bills)
                    
                    if len(bills) < 250 or offset >= limit:
                        break
                    offset += 250
                    time.sleep(0.3)
        
        logger.info(f"Total enacted bills found: {len(all_bills)}")
        return all_bills
    
    def _is_bill_enacted(self, bill: Dict) -> bool:
        action_text = bill.get('latestAction', {}).get('text', '').lower()
        return any(keyword in action_text for keyword in [
            'became public law', 'became private law', 'signed by president', 
            'public law no.', 'private law no.'
        ])
    
    def get_bill_subjects(self, congress: int, bill_type: str, bill_number: str) -> List[str]:
        data = self._make_request(f"bill/{congress}/{bill_type}/{bill_number}/subjects")
        subjects = []
        if 'subjects' in data and 'legislativeSubjects' in data['subjects']:
            subjects = [s['name'] for s in data['subjects']['legislativeSubjects'] if 'name' in s]
        return subjects
    
    def get_bill_xml_url(self, congress: int, bill_type: str, bill_number: str) -> Optional[str]:
        data = self._make_request(f"bill/{congress}/{bill_type}/{bill_number}/text")
        if 'textVersions' in data:
            version_types = ['Public Law', 'Enrolled Bill', 'Engrossed in House', 'Engrossed in Senate']
            
            for preferred_type in version_types:
                for version in data['textVersions']:
                    if version.get('type') == preferred_type:
                        for fmt in version.get('formats', []):
                            if fmt.get('type') == 'XML':
                                logger.info(f"Found XML URL for {bill_type.upper()}.{bill_number}: {preferred_type}")
                                return fmt.get('url')
            
            for version in data['textVersions']:
                for fmt in version.get('formats', []):
                    if 'xml' in fmt.get('type', '').lower():
                        logger.info(f"Found XML URL for {bill_type.upper()}.{bill_number}: {version.get('type')}")
                        return fmt.get('url')
        return None
    
    def download_and_clean_xml(self, xml_url: str) -> Optional[str]:
        try:
            logger.info(f"Downloading XML from: {xml_url}")
            response = requests.get(xml_url, timeout=30)
            response.raise_for_status()
            
            xml_content = response.text
            
            try:
                soup = BeautifulSoup(xml_content, 'xml')
                for script in soup(["script", "style"]):
                    script.decompose()
                text = soup.get_text(separator="\n", strip=True)
                
                logger.info(f"Successfully cleaned XML, text length: {len(text)}")
                return text
            
            except Exception as e:
                logger.warning(f"BeautifulSoup parsing failed: {e}, trying basic cleaning")
                text = re.sub(r'<[^>]+>', ' ', xml_content)
                text = re.sub(r'\s+', ' ', text).strip()
                return text
                
        except Exception as e:
            logger.error(f"Failed to download/clean XML: {e}")
            return None

class CongressLawsQdrantProcessor:
    KEYWORDS = [
        'investment', 'securities', 'mutual fund', 'etf', 'portfolio', 'asset management',
        'sec', 'investment advisor', 'broker-dealer', 'fiduciary', 'hedge fund',
        'retirement', 'pension', '401k', '401(k)', '403b', 'ira', 'roth', 'erisa',
        'defined contribution', 'defined benefit', 'employee benefit',
        'education', 'student loan', 'student aid', 'pell grant', '529 plan',
        'coverdell', 'education credit', 'scholarship', 'tuition',
        'health', 'medical', 'healthcare', 'health savings', 'hsa', 'medicare', 'medicaid',
        'affordable care', 'aca', 'health insurance', 'prescription drug',
        'insurance', 'life insurance', 'disability insurance', 'annuity',
        'insurance policy', 'variable annuity', 'universal life'
    ]
    
    def __init__(self, api_key: str):
        self.client = CongressAPIClient(api_key)
        self.qdrant_manager = QdrantManager()
        self.processed_count = 0
    
    def is_relevant_law(self, subjects: List[str], title: str) -> bool:
        text = " ".join(subjects + [title]).lower()
        return any(keyword.lower() in text for keyword in self.KEYWORDS)
    
    def _extract_law_number(self, action_text: str) -> Optional[str]:
        patterns = [r'public law no[:\s]+(\d+-\d+)', r'public law\s+(\d+-\d+)']
        for pattern in patterns:
            match = re.search(pattern, action_text.lower())
            if match:
                return match.group(1)
        return None
    
    def _create_law_id(self, bill: BillInfo) -> str:
        law_id_parts = [
            f"congress_{bill.congress}",
            f"{bill.bill_type}_{bill.bill_number}"
        ]
        if bill.law_number:
            law_id_parts.append(f"pl_{bill.law_number.replace('-', '_')}")
        
        return '_'.join(law_id_parts)
    
    def process_and_store_laws(self, congress_range: List[int] = None) -> int:
        if congress_range is None:
            congress_range = list(range(112, 120))
        
        logger.info(f"Searching for relevant laws in congresses: {congress_range}")
        logger.info("Processing all relevant laws found")
        
        all_bills = self.client.get_enacted_bills(congress_range, 1000)
        
        for bill in all_bills:
            try:
                congress = bill.get('congress')
                bill_type = bill.get('type', '').lower()
                bill_number = bill.get('number')
                title = bill.get('title', '')
                
                if not all([congress, bill_type, bill_number]):
                    continue
                
                subjects = self.client.get_bill_subjects(congress, bill_type, bill_number)
                
                if self.is_relevant_law(subjects, title):
                    logger.info(f"Found relevant law: {title[:60]}...")
                    
                    xml_url = self.client.get_bill_xml_url(congress, bill_type, bill_number)
                    if not xml_url:
                        logger.warning(f"No XML URL found for {bill_type.upper()}.{bill_number}")
                        continue
                    
                    xml_text = self.client.download_and_clean_xml(xml_url)
                    if not xml_text:
                        logger.warning(f"Failed to retrieve XML text for {bill_type.upper()}.{bill_number}")
                        continue
                    
                    latest_action = bill.get('latestAction', {})
                    law_number = self._extract_law_number(latest_action.get('text', ''))
                    
                    bill_info = BillInfo(
                        congress=congress,
                        bill_type=bill_type,
                        bill_number=bill_number,
                        title=title,
                        enacted_date=latest_action.get('actionDate'),
                        law_number=law_number
                    )
                    
                    law_id = self._create_law_id(bill_info)
                    logger.info(f"Processing law: {law_id}")
                    
                    chunks_count = self.qdrant_manager.process_and_store_law(xml_text, law_id)
                    logger.info(f"Saved {chunks_count} chunks for {law_id}")
                    
                    self.processed_count += 1
                    
                time.sleep(0.25)
                
            except Exception as e:
                logger.error(f"Error processing bill: {e}")
                continue
        
        logger.info(f"Successfully processed and stored {self.processed_count} laws in Qdrant")
        return self.processed_count