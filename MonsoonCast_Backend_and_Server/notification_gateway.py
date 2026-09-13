"""
notification_gateway.py

Pushes advisory text to farmers via WhatsApp (Twilio WhatsApp API / Meta
Cloud API) or plain SMS. Kept provider-swappable behind NotificationGateway
because this is just for SIH but after that we can swith to Twilio and switch to Meta's WhatsApp Business
Cloud API later without touching the rest of the backend.
It makes my later work easier.

Farmer registry: farmers.json  ->  [{"phone": "+91XXXXXXXXXX", "grid_key": "21.15_81.85",
                                     "crops": ["Rice"], "language": "hi"}, ...]

Env vars required (Twilio):
  TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN, TWILIO_WHATSAPP_FROM (e.g. 'whatsapp:+91XXXXXXXXXX')
"""

from __future__ import annotations

import json
import os
import requests
from pathlib import Path
from typing import Any
from dataclasses import dataclass


# from twilio.rest import Client  # for the time we start using Twilio


@dataclass
class Farmer:
    phone: str
    grid_key: str
    crops: list[str]
    language: str   # 'en' | 'hi' | 'or' and we will supposr more later hence this structure.

def load_farmers(path: Path) -> list[Farmer]:
    raw = json.loads(path.read_text(encoding='utf-8'))
    return [Farmer(**f) for f in raw]

def pick_highest_priority_advisory(advisories: list[dict[str, Any]], crops: list[str]) -> dict[str, Any] | None:
    """Choose the most urgent (7d bucket, highest risk_level, matching farmer's crops) advisory to send."""
    risk_rank = {'high': 2, 'moderate': 1, 'low': 0}
    candidates = [a for a in advisories if a['crop'] in crops]
    if not candidates:
        return None
    candidates.sort(key=lambda a: (a['lead_bucket'] != '7d', -risk_rank.get(a['risk_level'], 0)))
    return candidates[0]

class NotificationGateway:
    def __init__(self):
        # Local Android SMS Gate Configuration for Android sms sender app called SMSGate
        self.sms_api_url = os.getenv("SMS_GATEWAY_URL")
        self.sms_user = os.getenv("SMS_GATEWAY_USER")
        self.sms_pass = os.getenv("SMS_GATEWAY_KEY")

        # Local WhatsApp Express Bridge is currently using the private phone for testing which as said above will be swapped with business number
        self.wa_api_url = os.getenv("WA_GATEWAY_URL", "http://localhost:3000/send-message")

        # Twilio Production Configuration (Uncomment for professional deployment)
        # self.account_sid = os.getenv("TWILIO_ACCOUNT_SID")
        # self.auth_token = os.getenv("TWILIO_AUTH_TOKEN")
        # self.twilio_wa_from = os.getenv("TWILIO_WHATSAPP_FROM", "whatsapp:+14155238886")
        # self.twilio_sms_from = os.getenv("TWILIO_SMS_FROM", "+1234567890")
        # if self.account_sid and self.auth_token:
        #     self.client = Client(self.account_sid, self.auth_token)

    def send_sms(self, phone: str, text: str):
        """Sends SMS via local Android SMS Gate."""
        # Clean phone number format
        formatted_phone = phone if phone.startswith("+") else f"+91{phone}"

        payload = {
            "phoneNumbers": [formatted_phone],
            "message": text
        }
        
        res = requests.post(
            self.sms_api_url, 
            json=payload, 
            auth=(self.sms_user, self.sms_pass), 
            timeout=10
        )
        res.raise_for_status()
        return res.json()

        # Twilio SMS fallback
        # message = self.client.messages.create(
        #     body=text,
        #     from_=self.twilio_sms_from,
        #     to=formatted_phone
        # )
        # return message.sid

    def send_whatsapp(self, phone: str, text: str):
        """Sends WhatsApp message via local Node.js bridge."""
        payload = {"phone": phone, "message": text}
        res = requests.post(self.wa_api_url, json=payload, timeout=10)
        res.raise_for_status()
        return res.json()

        # Twilio WhatsApp fallback
        # message = self.client.messages.create(
        #     body=text,
        #     from_=self.twilio_wa_from,
        #     to=f"whatsapp:{phone}"
        # )
        # return message.sid

def dispatch_advisories(farmers: list[Farmer], advisories_by_grid: dict[str, list[dict[str, Any]]],
                         gateway: NotificationGateway | None = None) -> list[dict[str, Any]]:
    """
    advisories_by_grid: {grid_key: [advisory, ...]} -- e.g. run
    advisory_engine.generate_advisories() per cell and key the results by grid_key.
    gateway=None -> dry run (prints, no account/credentials needed). Pass a real
    NotificationGateway() to actually send.
    """
    results = []
    for farmer in farmers:
        advisories = advisories_by_grid.get(farmer.grid_key, [])
        chosen = pick_highest_priority_advisory(advisories, farmer.crops)
        if not chosen:
            continue
        text = chosen['text'].get(farmer.language, chosen['text']['en'])
        record = {'phone': farmer.phone, 'grid_key': farmer.grid_key, 'text': text, 'action_key': chosen['action_key']}
        if gateway is None:
            print(f'[DRY RUN] -> {farmer.phone}: {text}')
            record['status'] = 'dry_run'
        else:
            try:
                record['message_sid'] = gateway.send(farmer.phone, text)
                record['status'] = 'sent'
            except Exception as exc:  # noqa: BLE001 -- log & continue, one failed message shouldn't stop the batch
                record['status'] = f'failed: {exc}'
        results.append(record)
    return results


if __name__ == '__main__':
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument('--farmers', type=Path, default=Path('farmers.json'))
    parser.add_argument('--advisories-dir', type=Path, default=Path('data/advisories'),
                         help='Directory of {grid_key}.json files, each a list of advisories.')
    parser.add_argument('--send', action='store_true', help='Actually send via Twilio (default is dry-run print).')
    args = parser.parse_args()

    farmers_list = load_farmers(args.farmers)
    advisories_map = {
        p.stem: json.loads(p.read_text(encoding='utf-8'))
        for p in args.advisories_dir.glob('*.json')
    }
    gw = NotificationGateway() if args.send else None
    dispatch_advisories(farmers_list, advisories_map, gateway=gw)
