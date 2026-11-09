from pathlib import Path
import time
from typing import Optional, List, Dict, Any
import jwt
import httpx

from app.core.config import (
    GITHUB_APP_ID,
    GITHUB_PRIVATE_KEY,
    GITHUB_PRIVATE_KEY_PATH,
    GITHUB_API_BASE_URL
)


class GitHubAppService:
    """
    Manages GitHub App authentication, installation access tokens,
    and API communication with the GitHub REST API.
    """

    def __init__(
        self,
        app_id: Optional[str] = None,
        private_key: Optional[str] = None,
        base_url: Optional[str] = None
    ):
        self.app_id = app_id or GITHUB_APP_ID
        self.base_url = (base_url or GITHUB_API_BASE_URL).rstrip("/")
        self.private_key = private_key or self._load_private_key()
        self._token_cache: Dict[int, Dict[str, Any]] = {}

    def _load_private_key(self) -> str:
        if GITHUB_PRIVATE_KEY:
            return GITHUB_PRIVATE_KEY
        if GITHUB_PRIVATE_KEY_PATH and Path(GITHUB_PRIVATE_KEY_PATH).is_file():
            return Path(GITHUB_PRIVATE_KEY_PATH).read_text(encoding="utf-8")
        return ""

    def generate_jwt(self, expiration_seconds: int = 600) -> str:
        """
        Generate a RS256 JWT to authenticate as the GitHub App.
        """
        if not self.app_id or not self.private_key:
            raise ValueError("GitHub App ID and Private Key are required to generate JWT.")

        now = int(time.time())
        payload = {
            "iat": now - 60,  # 60s in the past to compensate for clock drift
            "exp": now + expiration_seconds,
            "iss": self.app_id
        }
        return jwt.encode(payload, self.private_key, algorithm="RS256")

    def get_installation_access_token(self, installation_id: int) -> str:
        """
        Retrieve or refresh a scoped installation token for a specific installation.
        """
        now = time.time()
        cached = self._token_cache.get(installation_id)
        if cached and cached["expires_at"] > now + 60:
            return cached["token"]

        app_jwt = self.generate_jwt()
        headers = {
            "Authorization": f"Bearer {app_jwt}",
            "Accept": "application/vnd.github+json"
        }

        url = f"{self.base_url}/app/installations/{installation_id}/access_tokens"
        with httpx.Client(timeout=10.0) as client:
            response = client.post(url, headers=headers)
            response.raise_for_status()
            data = response.json()

        token = data["token"]
        # Default expiry is 1 hour
        self._token_cache[installation_id] = {
            "token": token,
            "expires_at": now + 3500
        }
        return token

    def list_accessible_repositories(self, installation_id: int) -> List[Dict[str, Any]]:
        """
        Retrieve all repositories accessible by the specified installation.
        """
        token = self.get_installation_access_token(installation_id)
        headers = {
            "Authorization": f"Bearer {token}",
            "Accept": "application/vnd.github+json"
        }

        url = f"{self.base_url}/installation/repositories"
        with httpx.Client(timeout=10.0) as client:
            response = client.get(url, headers=headers)
            response.raise_for_status()
            data = response.json()

        repos = []
        for r in data.get("repositories", []):
            repos.append({
                "id": r["id"],
                "name": r["name"],
                "full_name": r["full_name"],
                "owner": r["owner"]["login"],
                "default_branch": r.get("default_branch", "main"),
                "private": r.get("private", False),
                "html_url": r.get("html_url", "")
            })
        return repos

    def get_pull_request_files(self, owner: str, repo: str, pull_number: int, installation_id: Optional[int] = None) -> List[Dict[str, Any]]:
        """
        Retrieve list of changed files for a Pull Request with their patch/status.
        """
        headers = {"Accept": "application/vnd.github+json"}
        if installation_id:
            token = self.get_installation_access_token(installation_id)
            headers["Authorization"] = f"Bearer {token}"

        url = f"{self.base_url}/repos/{owner}/{repo}/pulls/{pull_number}/files"
        with httpx.Client(timeout=10.0) as client:
            response = client.get(url, headers=headers)
            response.raise_for_status()
            return response.json()

    def get_repository_installation(self, owner: str, repo: str) -> Optional[int]:
        """
        Retrieve installation ID for a specific repository if the GitHub App is installed.
        Returns None if the App is not installed on the repository or App credentials are unset.
        """
        if not self.app_id or not self.private_key:
            return None
        app_jwt = self.generate_jwt()
        headers = {
            "Authorization": f"Bearer {app_jwt}",
            "Accept": "application/vnd.github+json"
        }
        url = f"{self.base_url}/repos/{owner}/{repo}/installation"
        with httpx.Client(timeout=10.0) as client:
            resp = client.get(url, headers=headers)
            if resp.status_code == 404:
                return None
            resp.raise_for_status()
            data = resp.json()
            return data.get("id")

    def get_repository(self, owner: str, repo: str, installation_id: Optional[int] = None) -> Dict[str, Any]:
        """
        Retrieve repository metadata from GitHub REST API.
        """
        headers = {"Accept": "application/vnd.github+json"}
        if installation_id:
            token = self.get_installation_access_token(installation_id)
            headers["Authorization"] = f"Bearer {token}"
        elif self.app_id and self.private_key:
            try:
                inst_id = self.get_repository_installation(owner, repo)
                if inst_id:
                    token = self.get_installation_access_token(inst_id)
                    headers["Authorization"] = f"Bearer {token}"
            except Exception:
                pass

        url = f"{self.base_url}/repos/{owner}/{repo}"
        with httpx.Client(timeout=10.0) as client:
            resp = client.get(url, headers=headers)
            resp.raise_for_status()
            return resp.json()

    def resolve_commit_sha(self, owner: str, repo: str, ref: str, installation_id: Optional[int] = None) -> Optional[str]:
        """
        Resolve a branch, tag, or commit reference to a full 40-character commit SHA.
        """
        headers = {"Accept": "application/vnd.github+json"}
        if installation_id:
            token = self.get_installation_access_token(installation_id)
            headers["Authorization"] = f"Bearer {token}"
        elif self.app_id and self.private_key:
            try:
                inst_id = self.get_repository_installation(owner, repo)
                if inst_id:
                    token = self.get_installation_access_token(inst_id)
                    headers["Authorization"] = f"Bearer {token}"
            except Exception:
                pass

        url = f"{self.base_url}/repos/{owner}/{repo}/commits/{ref}"
        with httpx.Client(timeout=10.0) as client:
            resp = client.get(url, headers=headers)
            if resp.status_code == 200:
                data = resp.json()
                return data.get("sha")
            return None
