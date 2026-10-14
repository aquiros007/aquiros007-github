#!/usr/bin/env python3
"""
LinkedIn publisher — NexusIQ Strategies
Reads today's post from campaign JSONs and publishes to LinkedIn ugcPosts API.

Required env vars:
  LINKEDIN_ACCESS_TOKEN  OAuth 2.0 access token (expires every 60 days)
  LINKEDIN_PERSON_URN    e.g. urn:li:person:AbCdEfG123

Optional:
  LINKEDIN_PUBLISH_DATE  Override today's date (YYYY-MM-DD) for manual triggers
"""
import json
import os
import sys
from datetime import datetime, timezone, timedelta
from pathlib import Path
import urllib.request
import urllib.error

LINKEDIN_API = "https://api.linkedin.com/v2"


def get_cr_date() -> str:
    cr_tz = timezone(timedelta(hours=-6))
    return datetime.now(cr_tz).strftime("%Y-%m-%d")


def load_campaigns(campaigns_dir: Path) -> list[dict]:
    campaigns = []
    for f in sorted(campaigns_dir.glob("*.json")):
        try:
            with open(f, encoding="utf-8") as fp:
                campaigns.append((f, json.load(fp)))
        except json.JSONDecodeError as e:
            print(f"WARN: Skipping malformed {f.name}: {e}")
    return campaigns


def find_today_post(campaigns, target_date: str):
    publishable = {"READY_TO_PUBLISH", "IMAGE_READY"}
    for (path, campaign) in campaigns:
        for post in campaign.get("posts", []):
            if post.get("date") == target_date and post.get("status") in publishable:
                return path, campaign, post
    return None, None, None


def register_image_upload(token: str, person_urn: str) -> tuple[str, str] | tuple[None, None]:
    """Returns (upload_url, asset_urn) or (None, None) on failure."""
    payload = {
        "registerUploadRequest": {
            "recipes": ["urn:li:digitalmediaRecipe:feedshare-image"],
            "owner": person_urn,
            "serviceRelationships": [{
                "relationshipType": "OWNER",
                "identifier": "urn:li:userGeneratedContent"
            }]
        }
    }
    req = urllib.request.Request(
        f"{LINKEDIN_API}/assets?action=registerUpload",
        data=json.dumps(payload).encode(),
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
            "X-Restli-Protocol-Version": "2.0.0",
        }
    )
    try:
        with urllib.request.urlopen(req) as resp:
            result = json.loads(resp.read())
        mechanism = result["value"]["uploadMechanism"]
        upload_url = mechanism["com.linkedin.digitalmedia.uploading.MediaUploadHttpRequest"]["uploadUrl"]
        asset_urn = result["value"]["asset"]
        return upload_url, asset_urn
    except Exception as e:
        print(f"WARN: Failed to register image upload: {e}")
        return None, None


def upload_image(token: str, upload_url: str, image_url: str) -> bool:
    try:
        with urllib.request.urlopen(image_url) as r:
            image_data = r.read()
    except Exception as e:
        print(f"WARN: Failed to fetch image from {image_url}: {e}")
        return False

    req = urllib.request.Request(
        upload_url,
        data=image_data,
        method="PUT",
        headers={"Authorization": f"Bearer {token}"}
    )
    try:
        with urllib.request.urlopen(req):
            pass
        return True
    except Exception as e:
        print(f"WARN: Failed to upload image to LinkedIn: {e}")
        return False


def publish_to_linkedin(token: str, person_urn: str, content: str, image_url: str | None) -> str | None:
    """Publishes post, returns LinkedIn post ID on success or None on failure."""
    asset_urn = None
    if image_url:
        upload_url, asset_urn = register_image_upload(token, person_urn)
        if upload_url and asset_urn:
            if not upload_image(token, upload_url, image_url):
                asset_urn = None  # Fall back to text-only
        else:
            asset_urn = None

    if asset_urn:
        share_content = {
            "shareCommentary": {"text": content},
            "shareMediaCategory": "IMAGE",
            "media": [{
                "status": "READY",
                "description": {"text": ""},
                "media": asset_urn,
                "title": {"text": ""}
            }]
        }
    else:
        share_content = {
            "shareCommentary": {"text": content},
            "shareMediaCategory": "NONE"
        }

    payload = {
        "author": person_urn,
        "lifecycleState": "PUBLISHED",
        "specificContent": {
            "com.linkedin.ugc.ShareContent": share_content
        },
        "visibility": {
            "com.linkedin.ugc.MemberNetworkVisibility": "PUBLIC"
        }
    }

    req = urllib.request.Request(
        f"{LINKEDIN_API}/ugcPosts",
        data=json.dumps(payload).encode(),
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
            "X-Restli-Protocol-Version": "2.0.0",
        }
    )
    try:
        with urllib.request.urlopen(req) as resp:
            result = json.loads(resp.read())
            post_id = result.get("id", "")
            print(f"✓ Published: {post_id}")
            return post_id
    except urllib.error.HTTPError as e:
        body = e.read().decode()
        print(f"✗ LinkedIn API error {e.code}: {body}")
        return None
    except Exception as e:
        print(f"✗ Unexpected error: {e}")
        return None


def mark_published(campaign_path: Path, post_id: str, linkedin_id: str) -> None:
    with open(campaign_path, encoding="utf-8") as f:
        data = json.load(f)
    for post in data.get("posts", []):
        if post["id"] == post_id:
            post["status"] = "PUBLISHED"
            post["linkedin_post_id"] = linkedin_id
            post["published_at"] = datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")
            break
    with open(campaign_path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    print(f"✓ Status updated in {campaign_path.name}")


def main():
    token = os.environ.get("LINKEDIN_ACCESS_TOKEN", "").strip()
    person_urn = os.environ.get("LINKEDIN_PERSON_URN", "").strip()

    if not token or not person_urn:
        print("ERROR: LINKEDIN_ACCESS_TOKEN and LINKEDIN_PERSON_URN env vars required.")
        sys.exit(1)

    target_date = (
        os.environ.get("LINKEDIN_PUBLISH_DATE", "").strip()
        or (sys.argv[1] if len(sys.argv) > 1 else "")
        or get_cr_date()
    )
    print(f"Target date: {target_date}")

    campaigns_dir = Path(__file__).parent.parent / "data" / "campaigns"
    campaigns = load_campaigns(campaigns_dir)

    campaign_path, campaign, post = find_today_post(campaigns, target_date)

    if post is None:
        print(f"No publishable post found for {target_date}.")
        sys.exit(0)

    print(f"Post: {post['id']} — {post.get('topic', '')}")

    content = post.get("content", "").strip()
    if not content:
        print(f"ERROR: Post {post['id']} has no 'content' field. Aborting.")
        sys.exit(1)

    image_url = (post.get("image") or {}).get("url")

    linkedin_id = publish_to_linkedin(token, person_urn, content, image_url)

    if linkedin_id:
        mark_published(campaign_path, post["id"], linkedin_id)
    else:
        print("Publishing failed — campaign JSON not modified.")
        sys.exit(1)


if __name__ == "__main__":
    main()
