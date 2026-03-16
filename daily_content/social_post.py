"""
social_post.py
--------------
Posts generated content to LinkedIn and Instagram via their official APIs.

LinkedIn API docs:  https://learn.microsoft.com/en-us/linkedin/marketing/
Instagram Graph API: https://developers.facebook.com/docs/instagram-api/

SETUP REQUIRED:
  1. LinkedIn: Create an app at https://developer.linkedin.com
               Request scopes: w_organization_social OR w_member_social
               Generate access token via OAuth 2.0

  2. Instagram: Create a Meta app at https://developers.facebook.com
                Connect your Instagram Professional account to a Facebook Page
                Request permissions: instagram_content_publish, pages_manage_posts
                Generate a long-lived Page Access Token
"""

import os
import time
from pathlib import Path
from typing import Optional

import requests


# ── LinkedIn ──────────────────────────────────────────────────────────────────

class LinkedInPoster:
    BASE_URL = "https://api.linkedin.com/v2"

    def __init__(self, access_token: str, organization_id: Optional[str] = None,
                 person_urn: Optional[str] = None):
        self.token    = access_token
        self.org_id   = organization_id
        self.person   = person_urn
        self.headers  = {
            "Authorization": f"Bearer {self.token}",
            "Content-Type":  "application/json",
            "X-Restli-Protocol-Version": "2.0.0",
        }

    def _author_urn(self) -> str:
        if self.org_id:
            # Accept both "12345678" and "urn:li:organization:12345678"
            if self.org_id.startswith("urn:"):
                return self.org_id
            return f"urn:li:organization:{self.org_id}"
        if self.person:
            if self.person.startswith("urn:"):
                return self.person
            return f"urn:li:person:{self.person}"
        raise ValueError("Provide organization_id or person_urn in config.")

    def post_text(self, text: str) -> dict:
        """Post a text-only LinkedIn update."""
        payload = {
            "author":  self._author_urn(),
            "lifecycleState": "PUBLISHED",
            "specificContent": {
                "com.linkedin.ugc.ShareContent": {
                    "shareCommentary": {"text": text},
                    "shareMediaCategory": "NONE",
                }
            },
            "visibility": {"com.linkedin.ugc.MemberNetworkVisibility": "PUBLIC"},
        }
        r = requests.post(f"{self.BASE_URL}/ugcPosts",
                          json=payload, headers=self.headers)
        r.raise_for_status()
        print(f"  ✅ LinkedIn post published  (id: {r.headers.get('x-restli-id', '?')})")
        return r.json() if r.text else {"status": "published"}

    def post_with_image(self, text: str, image_path: Path) -> dict:
        """Post a LinkedIn update with an image."""
        # Step 1: Register upload
        register_payload = {
            "registerUploadRequest": {
                "recipes": ["urn:li:digitalmediaRecipe:feedshare-image"],
                "owner":   self._author_urn(),
                "serviceRelationships": [{
                    "relationshipType": "OWNER",
                    "identifier": "urn:li:userGeneratedContent",
                }],
            }
        }
        r1 = requests.post(
            f"{self.BASE_URL}/assets?action=registerUpload",
            json=register_payload, headers=self.headers
        )
        r1.raise_for_status()
        resp1       = r1.json()
        upload_url  = resp1["value"]["uploadMechanism"]["com.linkedin.digitalmedia.uploading.MediaUploadHttpRequest"]["uploadUrl"]
        asset_urn   = resp1["value"]["asset"]

        # Step 2: Upload image bytes
        with open(image_path, "rb") as fh:
            img_bytes = fh.read()
        r2 = requests.put(upload_url, data=img_bytes,
                          headers={"Authorization": f"Bearer {self.token}"})
        r2.raise_for_status()

        # Step 3: Publish post with asset
        payload = {
            "author": self._author_urn(),
            "lifecycleState": "PUBLISHED",
            "specificContent": {
                "com.linkedin.ugc.ShareContent": {
                    "shareCommentary": {"text": text},
                    "shareMediaCategory": "IMAGE",
                    "media": [{
                        "status": "READY",
                        "description": {"text": ""},
                        "media": asset_urn,
                        "title": {"text": ""},
                    }],
                }
            },
            "visibility": {"com.linkedin.ugc.MemberNetworkVisibility": "PUBLIC"},
        }
        r3 = requests.post(f"{self.BASE_URL}/ugcPosts",
                           json=payload, headers=self.headers)
        r3.raise_for_status()
        print(f"  ✅ LinkedIn image post published  (id: {r3.headers.get('x-restli-id', '?')})")
        return r3.json() if r3.text else {"status": "published"}


# ── Instagram ─────────────────────────────────────────────────────────────────

class InstagramPoster:
    BASE_URL = "https://graph.facebook.com/v19.0"

    def __init__(self, access_token: str, account_id: str):
        self.token      = access_token
        self.account_id = account_id

    def _params(self, **kwargs) -> dict:
        return {"access_token": self.token, **kwargs}

    def post_image(self, image_url: str, caption: str) -> dict:
        """
        Post a single image to Instagram.
        image_url must be a publicly accessible URL (not a local path).
        Use post_image_from_file() to auto-host locally.
        """
        # Step 1: Create media container
        r1 = requests.post(
            f"{self.BASE_URL}/{self.account_id}/media",
            params=self._params(image_url=image_url, caption=caption)
        )
        r1.raise_for_status()
        container_id = r1.json()["id"]

        # Step 2: Publish
        r2 = requests.post(
            f"{self.BASE_URL}/{self.account_id}/media_publish",
            params=self._params(creation_id=container_id)
        )
        r2.raise_for_status()
        print(f"  ✅ Instagram post published  (id: {r2.json().get('id', '?')})")
        return r2.json()

    def post_carousel(self, image_urls: list, caption: str) -> dict:
        """Post a carousel of images to Instagram."""
        # Step 1: Create a container for each image (no caption on children)
        child_ids = []
        for url in image_urls:
            r = requests.post(
                f"{self.BASE_URL}/{self.account_id}/media",
                params=self._params(image_url=url, is_carousel_item=True)
            )
            r.raise_for_status()
            child_ids.append(r.json()["id"])
            time.sleep(1)   # avoid rate limiting

        # Step 2: Create carousel container
        r2 = requests.post(
            f"{self.BASE_URL}/{self.account_id}/media",
            params=self._params(
                media_type="CAROUSEL",
                children=",".join(child_ids),
                caption=caption,
            )
        )
        r2.raise_for_status()
        carousel_id = r2.json()["id"]

        # Step 3: Publish
        r3 = requests.post(
            f"{self.BASE_URL}/{self.account_id}/media_publish",
            params=self._params(creation_id=carousel_id)
        )
        r3.raise_for_status()
        print(f"  ✅ Instagram carousel published  (id: {r3.json().get('id', '?')})")
        return r3.json()

    def post_reel(self, video_url: str, caption: str,
                  cover_url: Optional[str] = None) -> dict:
        """
        Post a Reel to Instagram.
        video_url must be publicly accessible (MP4, H.264).
        """
        params = self._params(
            media_type="REELS",
            video_url=video_url,
            caption=caption,
        )
        if cover_url:
            params["cover_url"] = cover_url

        r1 = requests.post(f"{self.BASE_URL}/{self.account_id}/media", params=params)
        r1.raise_for_status()
        container_id = r1.json()["id"]

        # Reels need processing time — poll status
        print("  ⏳ Waiting for reel to process...", end="", flush=True)
        for _ in range(30):
            time.sleep(5)
            r_check = requests.get(
                f"{self.BASE_URL}/{container_id}",
                params=self._params(fields="status_code")
            )
            status = r_check.json().get("status_code", "")
            if status == "FINISHED":
                break
            print(".", end="", flush=True)
        print()

        r2 = requests.post(
            f"{self.BASE_URL}/{self.account_id}/media_publish",
            params=self._params(creation_id=container_id)
        )
        r2.raise_for_status()
        print(f"  ✅ Instagram Reel published  (id: {r2.json().get('id', '?')})")
        return r2.json()


# ── NOTE: image hosting ───────────────────────────────────────────────────────
# The Instagram Graph API requires publicly accessible image/video URLs.
# For local development, options include:
#   1. Upload to an S3 bucket (boto3) and use the public URL
#   2. Use Cloudinary free tier (cloudinary.com) — simpler
#   3. Use ngrok to temporarily expose a local HTTP server
#
# In production (e.g. running on a VPS/cloud), your server's public IP works.
#
# Cloudinary example (requires: pip install cloudinary):
#
#   import cloudinary, cloudinary.uploader
#   cloudinary.config(cloud_name="...", api_key="...", api_secret="...")
#   result = cloudinary.uploader.upload(str(local_image_path))
#   public_url = result["secure_url"]


def upload_to_cloudinary(local_path: Path, cloud_name: str,
                          api_key: str, api_secret: str) -> str:
    """Upload a local image/video to Cloudinary and return public URL."""
    try:
        import cloudinary
        import cloudinary.uploader
    except ImportError:
        raise RuntimeError("Run: pip install cloudinary")

    cloudinary.config(cloud_name=cloud_name, api_key=api_key, api_secret=api_secret)
    result = cloudinary.uploader.upload(str(local_path), resource_type="auto")
    return result["secure_url"]


# ── High-level dispatcher ─────────────────────────────────────────────────────
def post_content(content: dict, image_paths: list, cfg: dict,
                 video_path: Optional[Path] = None) -> dict:
    """
    Route content to the right platform based on brand config.
    Returns posting result dict.
    """
    brand        = content["brand"]
    content_type = content["content_type"]
    platform     = content["platform"]
    caption      = content["copy"].get("caption", "")

    if cfg.get("posting", {}).get("dry_run", True):
        print(f"  🔵 DRY RUN — would post {content_type} to {platform} for {brand}")
        print(f"     Caption preview: {caption[:120]}...")
        return {"dry_run": True}

    # ── LinkedIn ──────────────────────────────────────────────────────────────
    if platform == "linkedin":
        li_cfg = cfg.get("linkedin", {})
        if not li_cfg.get("enabled"):
            print("  ⚠️  LinkedIn not enabled in config.yaml")
            return {}
        poster = LinkedInPoster(
            access_token=li_cfg["access_token"],
            organization_id=li_cfg.get("organization_id"),
            person_urn=li_cfg.get("person_urn"),
        )
        if image_paths:
            return poster.post_with_image(caption, image_paths[0])
        return poster.post_text(caption)

    # ── Instagram ─────────────────────────────────────────────────────────────
    if platform == "instagram":
        ig_cfg = cfg.get("instagram", {})
        if not ig_cfg.get("enabled"):
            print("  ⚠️  Instagram not enabled in config.yaml")
            return {}
        poster = InstagramPoster(
            access_token=ig_cfg["access_token"],
            account_id=ig_cfg["instagram_account_id"],
        )

        # NOTE: need public URLs — set cloudinary keys in config or host elsewhere
        cloudinary_cfg = cfg.get("cloudinary", {})

        if content_type == "reel" and video_path and video_path.exists():
            vid_url  = upload_to_cloudinary(video_path, **cloudinary_cfg)
            cover_url = None
            if image_paths:
                cover_url = upload_to_cloudinary(image_paths[0], **cloudinary_cfg)
            return poster.post_reel(vid_url, caption, cover_url)

        if content_type == "carousel" and len(image_paths) > 1:
            urls = [upload_to_cloudinary(p, **cloudinary_cfg) for p in image_paths]
            return poster.post_carousel(urls, caption)

        # Single image
        if image_paths:
            img_url = upload_to_cloudinary(image_paths[0], **cloudinary_cfg)
            return poster.post_image(img_url, caption)

    return {"error": f"Unknown platform: {platform}"}
