"""
bird_identifier.py — Claude AI bird species identification.

Sends a captured bird photo to the Claude API (vision) and returns
structured species information. Uses claude-haiku-4-5 for fast,
cost-effective identification on every detection event.
"""
import base64
import json
import os

import anthropic

import config

_SYSTEM_PROMPT = """\
You are an expert ornithologist and birdwatcher. A home bird feeder camera
has detected motion and captured a photo. Your job is to identify any bird
visible in the image.

The feeder is a circular ring style, viewed from the side, so birds may
appear in profile, from behind, or partially obscured. Do your best even
with partial views.

Always respond with a single JSON object — no extra text, no markdown fences.
Use exactly these keys:
{
  "species": "scientific name or 'Unknown'",
  "common_name": "common English name or 'Unknown'",
  "confidence": "high | medium | low | none",
  "description": "1-2 sentence description of the bird and any interesting fact",
  "notes": "brief note on view angle, lighting, or uncertainty if relevant"
}

If no bird is visible (false alarm, empty feeder, just leaves/wind), set
species and common_name to "No bird detected" and confidence to "none".
"""

_USER_PROMPT = (
    "Please identify the bird in this photo from my backyard feeder "
    "in Overland Park, Kansas."
)


class BirdIdentifier:
    def __init__(self):
        if not config.ANTHROPIC_API_KEY:
            raise ValueError(
                "ANTHROPIC_API_KEY is not set. "
                "Add it to your .env file. "
                "Get a free key at https://console.anthropic.com"
            )
        self.client = anthropic.Anthropic(api_key=config.ANTHROPIC_API_KEY)

    def identify(self, image_path: str) -> dict:
        """
        Identify the bird species in the given image file.

        Returns a dict with keys:
          species, common_name, confidence, description, notes
        On any error, returns safe fallback values.
        """
        if not os.path.exists(image_path):
            return self._fallback(f"Image file not found: {image_path}")

        try:
            image_data = self._encode_image(image_path)
        except Exception as exc:
            return self._fallback(f"Could not read image: {exc}")

        try:
            response = self.client.messages.create(
                model=config.CLAUDE_MODEL,
                max_tokens=512,
                system=_SYSTEM_PROMPT,
                messages=[
                    {
                        "role": "user",
                        "content": [
                            {
                                "type": "image",
                                "source": {
                                    "type": "base64",
                                    "media_type": "image/jpeg",
                                    "data": image_data,
                                },
                            },
                            {"type": "text", "text": _USER_PROMPT},
                        ],
                    }
                ],
            )
        except anthropic.AuthenticationError:
            return self._fallback("Invalid ANTHROPIC_API_KEY — check your .env file")
        except anthropic.RateLimitError:
            return self._fallback("Claude API rate limit reached — try again shortly")
        except anthropic.APIConnectionError:
            return self._fallback("Cannot reach Claude API — check internet connection")
        except anthropic.APIStatusError as exc:
            return self._fallback(f"Claude API error {exc.status_code}: {exc.message}")

        raw_text = next(
            (block.text for block in response.content if block.type == "text"), ""
        ).strip()

        return self._parse_response(raw_text)

    # ── Helpers ──────────────────────────────────────────────────────────────

    def _encode_image(self, image_path: str) -> str:
        """Read an image file and return base64-encoded string."""
        with open(image_path, "rb") as f:
            return base64.standard_b64encode(f.read()).decode("utf-8")

    def _parse_response(self, raw_text: str) -> dict:
        """Parse Claude's JSON response, with fallback for malformed output."""
        # Strip any accidental markdown code fences
        text = raw_text.strip().lstrip("```json").lstrip("```").rstrip("```").strip()

        try:
            data = json.loads(text)
            return {
                "species":     data.get("species",     "Unknown"),
                "common_name": data.get("common_name", "Unknown"),
                "confidence":  data.get("confidence",  "low"),
                "description": data.get("description", ""),
                "notes":       data.get("notes",       ""),
            }
        except (json.JSONDecodeError, ValueError):
            # Claude returned something but not valid JSON — extract what we can
            return {
                "species":     "Unknown",
                "common_name": "Unknown",
                "confidence":  "low",
                "description": raw_text[:200] if raw_text else "Identification unavailable",
                "notes":       "Response parsing error",
            }

    def _fallback(self, reason: str) -> dict:
        return {
            "species":     "Unknown",
            "common_name": "Unknown",
            "confidence":  "none",
            "description": "Bird identification unavailable.",
            "notes":       reason,
        }
