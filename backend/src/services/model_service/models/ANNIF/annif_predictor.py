import logging
import requests
from typing import Dict, List, Optional, Any
from bs4 import BeautifulSoup

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class AnnifPredictor:
    """Wrapper for ANNIF using Finto AI API"""

    def __init__(self, base_url: str = "https://ai.finto.fi/v1", available_projects: Dict = None):
        self.base_url = base_url
        self.available_projects = available_projects or {}
        self.default_project = "yso-en"
        logger.info(f"✅ ANNIF using Finto AI API. Projects: {list(self.available_projects.keys())}")

    @staticmethod
    def extract_text_from_html(html_content: str) -> str:
        """Extract text from HTML body tag"""
        try:
            soup = BeautifulSoup(html_content, 'html.parser')
            # Try to find body tag
            body = soup.find('body')
            if body:
                return body.get_text(separator=' ', strip=True)
            # If no body tag, extract all text
            return soup.get_text(separator=' ', strip=True)
        except Exception as e:
            logger.warning(f"Failed to parse HTML: {e}")
            return html_content  # Return original content as fallback

    def predict(
        self,
        text: str,
        project_id: Optional[str] = None,
        limit: int = 10,
        threshold: float = 0.0
    ) -> Dict[str, Any]:
        """Predict subjects/topics for the given text using Finto AI API"""
        try:
            project_to_use = project_id or self.default_project

            if project_to_use not in self.available_projects:
                return {
                    "success": False,
                    "error": f"Project '{project_to_use}' not available",
                    "available_projects": list(self.available_projects.keys())
                }

            # Call Finto AI suggest endpoint
            url = f"{self.base_url}/projects/{project_to_use}/suggest"
            params = {
                "limit": limit,
                "threshold": threshold
            }
            # Finto AI expects form-urlencoded data, not JSON
            form_data = {"text": text}

            response = requests.post(
                url,
                params=params,
                data=form_data,  # Use data= for form-urlencoded, not json=
                headers={'Content-Type': 'application/x-www-form-urlencoded'},
                timeout=30
            )
            response.raise_for_status()

            result = response.json()

            # Transform response to standard format
            subjects = []
            for item in result.get("results", []):
                subjects.append({
                    "uri": item.get("uri"),
                    "label": item.get("label"),
                    "score": float(item.get("score", 0.0))
                })

            return {
                "success": True,
                "results": subjects,
                "project_id": project_to_use,
                "count": len(subjects)
            }

        except requests.RequestException as e:
            logger.error(f"API request error: {e}")
            return {
                "success": False,
                "error": f"API request failed: {str(e)}"
            }
        except Exception as e:
            logger.error(f"Prediction error: {e}")
            return {
                "success": False,
                "error": str(e)
            }

    def predict_batch(
        self,
        documents: List[Dict[str, str]],
        project_id: Optional[str] = None,
        limit: int = 10,
        threshold: float = 0.0
    ) -> Dict[str, Any]:
        """Predict subjects/topics for multiple documents using batch endpoint"""
        try:
            project_to_use = project_id or self.default_project

            if project_to_use not in self.available_projects:
                return {
                    "success": False,
                    "error": f"Project '{project_to_use}' not available",
                    "available_projects": list(self.available_projects.keys())
                }

            # Call Finto AI batch suggest endpoint
            url = f"{self.base_url}/projects/{project_to_use}/suggest-batch"
            params = {
                "limit": limit,
                "threshold": threshold
            }
            # Note: Batch endpoint might still use JSON - check Finto AI docs if this fails
            # For now keeping it as JSON since batch is typically JSON
            data = {"documents": documents}

            response = requests.post(url, params=params, json=data, timeout=60)
            response.raise_for_status()

            result = response.json()

            return {
                "success": True,
                "results": result,
                "project_id": project_to_use
            }

        except requests.RequestException as e:
            logger.error(f"API request error: {e}")
            return {
                "success": False,
                "error": f"API request failed: {str(e)}"
            }
        except Exception as e:
            logger.error(f"Batch prediction error: {e}")
            return {
                "success": False,
                "error": str(e)
            }
