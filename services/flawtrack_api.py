"""
FlawTrack API v2.0 Integration
Simplified implementation focusing only on the new FlawTrack API
"""
import requests
import json
import time
import os
from datetime import datetime, timedelta
from typing import Dict, List, Optional
from models.database import db, Breach
import logging

logger = logging.getLogger(__name__)

class FlawTrackAPI:
    """FlawTrack API v2.0 integration for breach data retrieval and risk scoring

    Provides comprehensive access to the FlawTrack credentials database with
    advanced features like unified search, source separation, and deduplication.
    """

    def __init__(self, api_key: str, endpoint: str):
        self.api_key = api_key
        self.base_url = endpoint.rstrip('/')
        self.session = requests.Session()

        # FlawTrack API v2.0 uses X-API-Key header
        self.session.headers.update({
            'X-API-Key': api_key,
            'Content-Type': 'application/json'
        })
        logger.info(f"Initialized FlawTrack API v2.0 client with endpoint: {endpoint}")

    def get_breach_data(self, domain: str, search_type: str = 'domain') -> Optional[Dict]:
        """Get breach data for a single domain from FlawTrack API

        Args:
            domain: Domain name to search for
            search_type: 'domain' or 'service'

        Returns:
            List of credential records or None if API failed
        """
        # Check if FlawTrack scanning is disabled
        scanning_enabled = os.environ.get('FLAWTRACK_SCANNING_ENABLED', 'true').lower() == 'true'

        if not scanning_enabled:
            logger.info(f"FlawTrack scanning disabled for {domain} - returning None to mark as unknown")
            return None  # This will cause the contact to be marked as 'unknown'

        try:
            # Use unified search endpoint for best results
            url = f"{self.base_url}/api/credentials/search"
            payload = {
                "query": domain,
                "search_type": search_type
            }

            logger.info(f"FlawTrack API: Making request to {url} for domain {domain}")
            response = self.session.post(url, json=payload, timeout=30)
            logger.info(f"FlawTrack API: Received response {response.status_code} for domain {domain}")

            if response.status_code == 200:
                result = response.json()

                # Handle direct data response (new API format)
                if isinstance(result, dict) and 'data' in result:
                    data = result.get('data', [])
                    stats = result.get('stats', {})

                    logger.info(f"FlawTrack API success for {domain}: found {len(data)} credentials")
                    if stats:
                        logger.info(f"  - BigQuery results: {stats.get('bigquery_results', 0)}")
                        logger.info(f"  - Database results: {stats.get('database_results', 0)}")
                        logger.info(f"  - Duplicates removed: {stats.get('duplicates_removed', 0)}")

                    return data if len(data) > 0 else []

                # Handle legacy format with status field
                elif isinstance(result, dict) and result.get('status') == 'success':
                    data = result.get('data', [])
                    stats = result.get('stats', {})

                    logger.info(f"FlawTrack API success for {domain}: found {stats.get('total_results', len(data))} credentials")
                    logger.info(f"  - BigQuery results: {stats.get('bigquery_results', 0)}")
                    logger.info(f"  - Database results: {stats.get('database_results', 0)}")
                    logger.info(f"  - Duplicates removed: {stats.get('duplicates_removed', 0)}")

                    return data if len(data) > 0 else []
                else:
                    logger.warning(f"FlawTrack API unexpected response format for {domain}: {result}")
                    return None
            elif response.status_code == 401:
                logger.error(f"FlawTrack API authentication failed for {domain}: Invalid API key")
                return None
            elif response.status_code == 400:
                logger.error(f"FlawTrack API bad request for {domain}: Invalid query parameters")
                return None
            else:
                logger.warning(f"FlawTrack API returned {response.status_code} for {domain}")
                return None

        except Exception as e:
            logger.error(f"FlawTrack API exception for {domain}: {str(e)}")
            return None

    def batch_domain_lookup(self, domains: List[str], delay: float = 1.0, progress_callback=None, search_type: str = 'domain') -> Dict[str, Dict]:
        """Process multiple domains with rate limiting

        Args:
            domains: List of domain names to scan
            delay: Delay between requests (seconds)
            progress_callback: Optional callback function for progress updates
            search_type: 'domain' or 'service' search type

        Returns:
            Dictionary mapping domain names to breach data
        """
        results = {}

        for i, domain in enumerate(domains):
            logger.info(f"Processing domain {i+1}/{len(domains)}: {domain}")

            # Update progress callback
            if progress_callback:
                scan_progress = 50 + (i / len(domains)) * 20  # 50-70% range
                progress_callback(f"Scanning {domain} for breaches...", scan_progress,
                                domains_scanned=i, total_domains=len(domains), current_domain=domain)

            # Fetch from API
            breach_data = self.get_breach_data(domain, search_type)

            if breach_data is not None:
                # API succeeded - process the data
                risk_score = self.calculate_risk_score(breach_data)
                processed_data = self.process_breach_data(domain, breach_data, risk_score)
                results[domain] = processed_data

            else:
                # API failed or timed out - mark as unknown
                logger.warning(f"FlawTrack API failed for {domain} - marking as unknown")
                results[domain] = {
                    'domain': domain,
                    'breach_name': f"{domain} - Scan Incomplete",
                    'breach_year': None,
                    'records_affected': 0,
                    'data_types': "FlawTrack API unavailable - manual verification needed",
                    'risk_score': 0.0,
                    'severity': 'low',
                    'breach_status': 'unknown',
                    'raw_data': '{}'
                }

            # Rate limiting
            if i < len(domains) - 1:
                time.sleep(delay)

        return results

    def calculate_risk_score(self, breach_data: Dict) -> float:
        """Calculate risk score (not used in current implementation)"""
        return 0.0

    def process_breach_data(self, domain: str, raw_data, risk_score: float = 0.0) -> Dict:
        """Process FlawTrack data into structured breach information

        Args:
            domain: Domain name
            raw_data: Raw API response data
            risk_score: Calculated risk score

        Returns:
            Structured breach data dictionary
        """
        # Handle FlawTrack API format: list of credential records
        if isinstance(raw_data, list):
            if len(raw_data) > 0:
                # Found breaches - extract useful data for campaigns
                first_record = raw_data[0]

                # Extract breach year from various possible fields
                breach_year = (self._extract_year_from_created_at(first_record.get('created_at')) or
                             self._extract_year_from_created_at(first_record.get('date')) or
                             datetime.now().year - 1)

                records_affected = len(raw_data)

                # Get sample credentials for campaign use (first few records)
                sample_records = raw_data[:3]  # Get up to 3 sample records

                # Aggregate service names - handle both legacy and new API formats
                services = set()
                for record in raw_data:
                    # Try different field names for service
                    service = (record.get('service_name') or
                             record.get('url') or
                             record.get('host') or
                             '')
                    if service:
                        services.add(service)

                service_names = list(services)[:5]  # Top 5 services

                # Extract data sources if available (new API feature)
                sources = set()
                for record in raw_data:
                    source = record.get('source')
                    if source:
                        sources.add(source)

                return {
                    'domain': domain,
                    'breach_status': 'breached',
                    'records_affected': records_affected,
                    'breach_year': breach_year,
                    'services_affected': service_names,
                    'sample_records': sample_records,  # For campaign personalization
                    'breach_data': raw_data,  # Full data stored for reference
                    'data_sources': list(sources),  # New API feature: BigQuery/Database sources
                    'risk_score': risk_score,
                    'severity': self.get_severity_category(risk_score)
                }
            else:
                # Empty list = no breaches found
                return {
                    'domain': domain,
                    'breach_status': 'not_breached',
                    'records_affected': 0,
                    'breach_year': None,
                    'services_affected': [],
                    'sample_records': [],
                    'breach_data': [],
                    'data_sources': [],
                    'risk_score': 0.0,
                    'severity': 'low'
                }

        elif raw_data is None:
            # API failed or timed out
            return {
                'domain': domain,
                'breach_status': 'unknown',  # Didn't scan
                'records_affected': 0,
                'breach_year': None,
                'services_affected': [],
                'sample_records': [],
                'breach_data': None,
                'data_sources': [],
                'risk_score': 0.0,
                'severity': 'unknown'
            }

        else:
            # Unexpected format - treat as scan failure
            return {
                'domain': domain,
                'breach_status': 'unknown',
                'records_affected': 0,
                'breach_year': None,
                'services_affected': [],
                'sample_records': [],
                'breach_data': raw_data,
                'data_sources': [],
                'risk_score': 0.0,
                'severity': 'unknown'
            }

    def _extract_year_from_created_at(self, created_at_str: str) -> Optional[int]:
        """Extract year from FlawTrack created_at timestamp like '2024-08-02T01:56:08.653348Z'"""
        if not created_at_str:
            return None
        try:
            return int(created_at_str.split('-')[0])
        except (ValueError, IndexError, AttributeError):
            return None

    def get_severity_category(self, risk_score: float) -> str:
        """Convert risk score to severity category"""
        if risk_score >= 7.0:
            return 'high'
        elif risk_score >= 4.0:
            return 'medium'
        else:
            return 'low'

    # Health Check Methods
    def health_check(self) -> Dict:
        """Check FlawTrack API health status"""
        try:
            start_time = time.time()

            url = f"{self.base_url}/health"
            # Health endpoint doesn't require authentication
            response = requests.get(url, timeout=10)

            response_time_ms = int((time.time() - start_time) * 1000)

            if response.status_code == 200:
                health_data = response.json()
                return {
                    'status': 'healthy',
                    'healthy': True,
                    'message': 'API is running normally',
                    'response_time_ms': response_time_ms,
                    'api_version': 'v2.0 (New API)',
                    'service_info': health_data
                }
            else:
                return {
                    'status': 'unhealthy',
                    'healthy': False,
                    'message': f'Health check returned {response.status_code}',
                    'response_time_ms': response_time_ms,
                    'api_version': 'v2.0 (New API)'
                }
        except Exception as e:
            return {
                'status': 'error',
                'healthy': False,
                'message': f'Health check failed: {str(e)}',
                'response_time_ms': 0,
                'api_version': 'v2.0 (New API)'
            }

    # Advanced API Methods
    def search_by_service(self, service_name: str) -> Optional[List]:
        """Search credentials by service name"""
        try:
            return self.get_breach_data(service_name, 'service')
        except Exception as e:
            logger.error(f"Service search failed for {service_name}: {str(e)}")
            return None

    def get_bigquery_only_results(self, domain: str, search_type: str = 'domain') -> Optional[List]:
        """Get results from BigQuery only"""
        try:
            url = f"{self.base_url}/api/credentials/search/bigquery"
            payload = {
                "query": domain,
                "search_type": search_type
            }

            response = self.session.post(url, json=payload, timeout=30)

            if response.status_code == 200:
                result = response.json()
                if result.get('status') == 'success':
                    data = result.get('data', [])
                    logger.info(f"BigQuery search success for {domain}: found {len(data)} credentials")
                    return data

            return None
        except Exception as e:
            logger.error(f"BigQuery search failed for {domain}: {str(e)}")
            return None

    def get_database_only_results(self, domain: str, search_type: str = 'domain') -> Optional[List]:
        """Get results from PostgreSQL database only"""
        try:
            url = f"{self.base_url}/api/credentials/search/database"
            payload = {
                "query": domain,
                "search_type": search_type
            }

            response = self.session.post(url, json=payload, timeout=30)

            if response.status_code == 200:
                result = response.json()
                if result.get('status') == 'success':
                    data = result.get('data', [])
                    logger.info(f"Database search success for {domain}: found {len(data)} credentials")
                    return data

            return None
        except Exception as e:
            logger.error(f"Database search failed for {domain}: {str(e)}")
            return None

    def get_api_info(self) -> Dict:
        """Get information about the current API configuration"""
        return {
            'api_version': 'v2.0 (New API)',
            'endpoint': self.base_url,
            'has_health_check': True,
            'supports_service_search': True,
            'supports_source_separation': True,
            'supports_deduplication': True,
            'authentication_method': 'X-API-Key'
        }

    # Additional utility methods for email templates and breach samples
    def extract_breach_samples(self, raw_data, max_samples: int = 3, redaction_level: str = 'medium') -> List[str]:
        """Extract redacted sample credentials from breach data for email templates"""
        try:
            samples = []

            if isinstance(raw_data, list) and len(raw_data) > 0:
                # Extract samples from list of breach records
                for record in raw_data[:max_samples]:
                    email = record.get('email', '')
                    username = record.get('username', '')
                    service = record.get('service_name', '')

                    # Prioritize email, fallback to username
                    credential = email if email else username

                    if credential:
                        redacted = self._redact_credential(credential, redaction_level)
                        if service:
                            samples.append(f"{redacted} ({service})")
                        else:
                            samples.append(redacted)

            elif isinstance(raw_data, dict):
                # Single breach record
                email = raw_data.get('email', '')
                if email:
                    redacted = self._redact_credential(email, redaction_level)
                    samples.append(redacted)

            return samples[:max_samples]

        except Exception as e:
            logger.error(f"Error extracting breach samples: {str(e)}")
            return []

    def _redact_credential(self, credential: str, redaction_level: str = 'medium') -> str:
        """Redact credential for privacy protection"""
        try:
            if '@' in credential:  # Email address
                local, domain = credential.split('@', 1)

                if redaction_level == 'full':
                    # Show only first character and domain: j***@company.com
                    redacted_local = local[0] + '***' if len(local) > 0 else '***'
                elif redaction_level == 'medium':
                    # Show first 2 chars and last char: jo***n@company.com
                    if len(local) <= 3:
                        redacted_local = local[0] + '***'
                    else:
                        redacted_local = local[:2] + '***' + local[-1]
                elif redaction_level == 'minimal':
                    # Show first half: john***@company.com
                    mid_point = len(local) // 2
                    redacted_local = local[:mid_point] + '***'
                else:
                    redacted_local = local[0] + '***'

                return f"{redacted_local}@{domain}"
            else:
                # Username without @ symbol
                if redaction_level == 'full':
                    return credential[0] + '***' if len(credential) > 0 else '***'
                elif redaction_level == 'medium':
                    if len(credential) <= 3:
                        return credential[0] + '***'
                    else:
                        return credential[:2] + '***' + credential[-1]
                elif redaction_level == 'minimal':
                    mid_point = len(credential) // 2
                    return credential[:mid_point] + '***'
                else:
                    return credential[0] + '***'

        except Exception as e:
            logger.error(f"Error redacting credential: {str(e)}")
            return "***@***.com"

    def cache_breach_data(self, domain: str, processed_data: Dict):
        """Cache breach data in the database for future reference"""
        try:
            import json
            from datetime import datetime

            # Find existing breach record or create new one
            existing_breach = Breach.query.filter_by(domain=domain).first()

            if not existing_breach:
                existing_breach = Breach(domain=domain)
                db.session.add(existing_breach)

            # Update breach record with processed data
            existing_breach.breach_status = processed_data.get('breach_status', 'unknown')
            existing_breach.records_affected = processed_data.get('records_affected', 0)
            existing_breach.breach_year = processed_data.get('breach_year')
            existing_breach.risk_score = processed_data.get('risk_score', 0.0)
            existing_breach.severity = processed_data.get('severity', 'low')
            existing_breach.last_updated = datetime.utcnow()

            # Store raw breach data as JSON
            if 'breach_data' in processed_data:
                existing_breach.breach_data = json.dumps(processed_data['breach_data'])

            # Store additional metadata
            if 'services_affected' in processed_data:
                existing_breach.data_types = ', '.join(processed_data['services_affected'][:5])  # Store first 5 services

            # Create a breach name if not provided
            if processed_data['breach_status'] == 'breached':
                services = processed_data.get('services_affected', [])
                if services:
                    existing_breach.breach_name = f"{domain} - {services[0]} Breach {processed_data.get('breach_year', 'Recent')}"
                else:
                    existing_breach.breach_name = f"{domain} - Data Breach {processed_data.get('breach_year', 'Recent')}"
            else:
                existing_breach.breach_name = f"{domain} - No Breach Detected"

            db.session.commit()
            logger.info(f"Cached breach data for {domain}: {processed_data['breach_status']}")

        except Exception as e:
            logger.error(f"Failed to cache breach data for {domain}: {str(e)}")
            db.session.rollback()

    def get_breach_summary_for_email(self, domain: str) -> Dict:
        """Get breach summary formatted for email templates"""
        breach = Breach.query.filter_by(domain=domain).first()

        if not breach:
            return {
                'has_breach': False,
                'risk_level': 'low',
                'template_vars': {}
            }

        # Extract breach samples from raw data
        try:
            import json
            import os

            # Check if breach samples are enabled
            breach_sample_enabled = os.environ.get('BREACH_SAMPLE_ENABLED', 'true').lower() == 'true'

            if breach_sample_enabled:
                redaction_level = os.environ.get('BREACH_SAMPLE_REDACTION_LEVEL', 'medium')
                max_samples = int(os.environ.get('BREACH_SAMPLE_MAX_SAMPLES', '3'))

                raw_data = json.loads(breach.breach_data) if breach.breach_data else {}
                breach_samples = self.extract_breach_samples(raw_data, max_samples=max_samples, redaction_level=redaction_level)

                # Format samples for email display
                if breach_samples:
                    formatted_samples = "Sample exposed credentials:\n" + "\n".join([f"• {sample}" for sample in breach_samples])
                else:
                    formatted_samples = "Contact us for specific breach details"
            else:
                formatted_samples = "Contact us for specific breach details"

        except Exception as e:
            logger.error(f"Error processing breach samples for {domain}: {str(e)}")
            formatted_samples = "Contact us for specific breach details"

        return {
            'has_breach': True,
            'risk_level': breach.severity,
            'risk_score': breach.risk_score,
            'template_vars': {
                'breach_name': breach.breach_name,
                'breach_year': breach.breach_year,
                'records_affected': f"{breach.records_affected:,}" if breach.records_affected else "thousands of",
                'data_types': breach.data_types or "user credentials and personal information",
                'breach_sample': formatted_samples
            }
        }