from collections import deque
from datetime import datetime, timezone
import time
import re


DEFAULT_RAID_CONFIG = {
    "join_window_sec": 15,
    "message_window_sec": 20,
    "recent_join_ttl_sec": 600,
    "message_after_join_suspicion_sec": 20,
    "join_threshold": 5,
    "suspicious_message_threshold": 3,
    "new_account_max_age_days": 7,
    "new_account_ratio_threshold": 0.6,
    "suspected_raid_score": 3,
    "under_raid_score": 6,
}
#This is the default configuration of the anti-raid system, you can change it if you want to
#The values on the right are identified as the names on the left, simple and idiot-proof

URL_RE = re.compile(r'https?://|www\.')
DISCORD_INVITE_RE = re.compile(r'(discord\.gg/|discord\.com/invite/)')

#If it contains these, it can be a sign of a raid incoming, brace yourself

class GuildRaidData:
    def __init__(self):
        self.join_events = deque()
        self.suspicious_message_events = deque()
        self.recent_joins = {}
        self.current_state = "NORMAL"
        self.last_score = 0
        self.last_state_change = time.time()
        self.under_raid_since = None
#WE NEED ALL THE DATA!!!

class RaidDetector:
    def __init__(self):
        self.guild_data = {}

    def _get_guild_data(self, guild_id):
        if guild_id not in self.guild_data:
            self.guild_data[guild_id] = GuildRaidData()
        return self.guild_data[guild_id]
#If the server I'm veryfying is not currently saved, get all the server's needed data from the GuildRaidData class

    def _prune_guild_data(self, data, config):
        now = time.time()

        join_window = config["join_window_sec"]
        while data.join_events and (now - data.join_events[0][0]) > join_window:
            data.join_events.popleft()

        suspicious_window = config["message_window_sec"]
        while data.suspicious_message_events and (now - data.suspicious_message_events[0][0]) > suspicious_window:
            data.suspicious_message_events.popleft()

        recent_join_ttl = config["recent_join_ttl_sec"]
        expired_members = [
            member_id
            for member_id, joined_at in data.recent_joins.items()
            if (now - joined_at) > recent_join_ttl
        ]
        for member_id in expired_members:
            del data.recent_joins[member_id]
# If things start happening too fast (joins/messages), something's off... probably a raid

    def register_join(self, member, config=None):
        config = config or DEFAULT_RAID_CONFIG
        data = self._get_guild_data(member.guild.id)
        now = time.time()

        self._prune_guild_data(data, config)

        account_age_days = self._account_age_days(member)
        data.join_events.append((now, member.id, account_age_days))
        data.recent_joins[member.id] = now

        return self._evaluate_state(data, config)

    def _is_suspicious_message(self, message, joined_at, config):
        content = (message.content or "").lower()
        now = time.time()
        seconds_since_join = now - joined_at

        has_link = bool(URL_RE.search(content))
        has_invite = bool(DISCORD_INVITE_RE.search(content))
        too_soon = seconds_since_join <= config["message_after_join_suspicion_sec"]
        has_attachments = bool(message.attachments)

        if has_invite:
            return True, "contains_invite"
        if has_link:
            return True, "contains_link"
        if has_attachments and too_soon:
            return True, "attachment_too_soon"
        if too_soon and len(content) > 30:
            return True, "early_message"

        return False, None

    def register_message(self, message, config=None):
        config = config or DEFAULT_RAID_CONFIG
        if message.guild is None or message.author.bot:
            return None

        data = self._get_guild_data(message.guild.id)
        self._prune_guild_data(data, config)

        joined_at = data.recent_joins.get(message.author.id)
        if not joined_at:
            return None

        suspicious, reason = self._is_suspicious_message(message, joined_at, config)
        if suspicious:
            data.suspicious_message_events.append((time.time(), message.author.id, reason))

        return self._evaluate_state(data, config)

    def _calculate_score(self, data, config):
        score = 0

        join_count = len(data.join_events)
        suspicious_message_count = len(data.suspicious_message_events)

        new_account_count = sum(
            1 for _, _, age_days in data.join_events
            if age_days <= config["new_account_max_age_days"]
        )

        if join_count >= config["join_threshold"]:
            score += 3

        if join_count > 0:
            new_account_ratio = new_account_count / join_count
            if new_account_ratio >= config["new_account_ratio_threshold"]:
                score += 2

        if suspicious_message_count >= config["suspicious_message_threshold"]:
            score += 3

        return score

    def _evaluate_state(self, data, config):
        score = self._calculate_score(data, config)
        old_state = data.current_state
        new_state = old_state

        if score >= config["under_raid_score"]:
            new_state = "UNDER_RAID"
        elif score >= config["suspected_raid_score"]:
            new_state = "SUSPECTED"
        else:
            new_state = "NORMAL"

        changed = new_state != old_state

        data.last_score = score
        if changed:
            data.current_state = new_state
            data.last_state_change = time.time()
            if new_state == "UNDER_RAID":
                data.under_raid_since = time.time()
            elif new_state == "NORMAL":
                data.under_raid_since = None

        return {
            "changed": changed,
            "old_state": old_state,
            "new_state": new_state,
            "score": score,
            "join_count": len(data.join_events),
            "suspicious_message_count": len(data.suspicious_message_events),
        }

    def _account_age_days(self, member) -> int:
        now = datetime.now(timezone.utc)
        created_at = member.created_at

        if created_at.tzinfo is None:
            created_at = created_at.replace(tzinfo=timezone.utc)

        age = now - created_at
        return max(age.days, 0)
