"""
Stat id -> concrete AnyData class name map.

Each end-of-race stat is an AnyObjectHolder whose className is the concrete type
(UInt8/UInt16/UInt32/Float/StringStatistic). Applies to both AnyObjectHolder
paths: 101 (read/leaderboard) and 102 (end-of-race upload). 0xD6-0xF7 is a
contiguous UInt8 boolean-flag run (0/1).
"""

# stat id -> concrete AnyData class name
STAT_TYPE = {
    # --- named "career/online" stats (id table) ---
    0x01: "UInt32Statistic",  # net_total_distance_driven
    0x02: "UInt32Statistic",  # net_time_spent_driving
    0x04: "UInt32Statistic",  # net_number_of_wrecks
    0x05: "UInt32Statistic",  # net_flashbacks_used
    0x06: "FloatStatistic",  # net_longest_slide
    0x07: "FloatStatistic",  # net_longest_jump
    0x08: "FloatStatistic",
    0x09: "UInt16Statistic",  # net_total_num_rolls
    0x0A: "UInt8Statistic",  # net_average_finishing_position
    0x0B: "UInt16Statistic",  # net_clean_stages
    0x0C: "UInt8Statistic",
    0x0D: "UInt8Statistic",
    0x0E: "UInt32Statistic",
    0x11: "UInt8Statistic",
    0x14: "UInt16Statistic",
    0x15: "UInt16Statistic",
    0x16: "UInt32Statistic",  # net_car_total_distance
    0x17: "UInt32Statistic",  # net_car_total_time
    0x19: "UInt32Statistic",  # net_car_number_of_wrecks
    0x1A: "UInt32Statistic",
    0x1B: "FloatStatistic",  # net_car_longest_slide
    0x1C: "FloatStatistic",  # net_car_longest_jump
    0x1E: "UInt16Statistic",
    0x1F: "UInt8Statistic",  # net_car_average_finishing_position
    0x20: "UInt16Statistic",
    0x21: "FloatStatistic",
    0x22: "UInt8Statistic",
    0x23: "UInt8Statistic",
    0x28: "UInt16Statistic",
    0x29: "UInt16Statistic",
    0x2F: "UInt16Statistic",
    0x30: "UInt16Statistic",
    0x31: "UInt16Statistic",
    0x32: "UInt32Statistic",  # net_offline_xp
    0x33: "UInt8Statistic",
    0x35: "UInt16Statistic",  # net_won_races
    0x36: "UInt16Statistic",  # net_podiums
    0x37: "UInt16Statistic",  # net_num_races
    0x39: "UInt16Statistic",  # net_best_buddies
    # --- extended/session stats (unnamed in the table) ---
    0x46: "UInt32Statistic",
    0x47: "UInt32Statistic",
    0x48: "UInt8Statistic",
    0x49: "UInt8Statistic",
    0x4A: "FloatStatistic",
    0x4B: "FloatStatistic",
    0x4C: "FloatStatistic",
    0x4D: "UInt16Statistic",
    0x4E: "UInt8Statistic",
    0x4F: "UInt8Statistic",
    0x50: "UInt8Statistic",
    0x51: "UInt8Statistic",
    0x58: "UInt8Statistic",
    0x6E: "UInt32Statistic",
    0x6F: "StringStatistic",  # camera/config preference, e.g. "chase_far"
    0x70: "UInt32Statistic",
    0x71: "UInt32Statistic",
    0x72: "UInt32Statistic",
    0x73: "UInt32Statistic",
    0x74: "UInt32Statistic",
    0x77: "UInt8Statistic",
    # --- 0xC8..0xF7 flag block: 0xC9 is UInt32, all others UInt8 (0/1) ---
    0xC8: "UInt8Statistic",
    0xC9: "UInt32Statistic",
}
# 0xCA..0xF7 are all UInt8 boolean flags (contiguous run in the capture).
for _sid in range(0xCA, 0xF8):
    STAT_TYPE.setdefault(_sid, "UInt8Statistic")

# Stat id -> name.
STAT_NAME = {
    # --- registered career/profile stats ---
    0x01: "net_total_distance_driven",
    0x02: "net_time_spent_driving",
    0x03: "net_average_speed",
    0x04: "net_number_of_wrecks",
    0x05: "net_flashbacks_used",
    0x06: "net_longest_slide",
    0x07: "net_longest_jump",
    0x08: "net_longest_two_wheels",
    0x09: "net_total_num_rolls",
    0x0A: "net_average_finishing_position",
    0x0B: "net_clean_stages",
    0x0C: "net_favourite_car",
    0x0D: "net_favourite_track",
    0x11: "net_tournaments_entered",
    0x14: "net_car_combined_races",
    0x15: "net_car_combined_wins",
    0x16: "net_car_total_distance",
    0x17: "net_car_total_time",
    0x18: "net_car_average_speed",
    0x19: "net_car_number_of_wrecks",
    0x1B: "net_car_longest_slide",
    0x1C: "net_car_longest_jump",
    0x1F: "net_car_average_finishing_position",
    0x21: "net_car_highest_speed",
    0x32: "net_offline_xp",
    0x35: "net_won_races",
    0x36: "net_podiums",
    0x37: "net_num_races",
    0x38: "net_dirt_games_won",
    0x39: "net_best_buddies",
    0x3C: "net_online_wins",
    0x3D: "net_online_podiums",
    0x3E: "net_online_races",
    0x3F: "net_online_xp",
    0x0E: "raceTime_lap_ms",  # ?
    0x28: "perRaceCounter",  # ?
    0x46: "distanceTravelled",  # ?
    0x47: "raceTime_event_ms",  # ?
    0x4A: "longestSlide",  # ?
    0x4B: "longestJump",  # ?
    0x4C: "longestTimeOnTwoWheels",  # ?
    0x4D: "race_num_rolls",  # ?
    0x50: "vehicleId",  # ?
    0x51: "trackId",  # ?
    0x58: "liveryVariantId",  # ?
    0x6E: "playerXP",  # ?
    0x6F: "camera_view",  # ?
    0x1A: "flashbacks_total",  # ?
    0x49: "race_flashbacks",  # ?
    0x74: "car_context",  # ?
}
# --- achievement flags 0xc8..0xf7 ---
_ACH = {
    0xC8: 0,
    0xC9: 46,
    0xCA: 47,
    0xCB: 48,
    0xCC: 49,
    0xCD: 50,
    0xCE: 51,
    0xCF: 52,
    0xD0: 56,
    0xD1: 57,
    0xD2: 58,
    0xD3: 59,
    0xD4: 60,
    0xD5: 61,
    0xD6: 62,
    0xD7: 63,
    0xD8: 64,
    0xD9: 65,
    0xDA: 66,
    0xDB: 67,
    0xDC: 68,
    0xDD: 69,
    0xDE: 70,
    0xDF: 71,
    0xE0: 72,
    0xE1: 73,
    0xE2: 74,
    0xE3: 75,
    0xE4: 76,
    0xE5: 79,
    0xE6: 80,
    0xE7: 81,
    0xE8: 82,
    0xE9: 83,
    0xEA: 84,
    0xEB: 85,
    0xEC: 86,
    0xED: 87,
    0xEE: 88,
    0xEF: 89,
    0xF0: 90,
    0xF1: 91,
    0xF2: 92,
    0xF3: 93,
    0xF4: 94,
    0xF5: 95,
    0xF6: 96,
    0xF7: 97,
}
for _sid, _n in _ACH.items():
    STAT_NAME[_sid] = f"achievement_{_n:03d}"


def class_for(stat_id, default="UInt32Statistic"):

    return STAT_TYPE.get(stat_id, default)


# ---------------------------------------------------------------------------
# Read-path class map. On a stat read the client resolves the concrete type from
# the stat id via Quazal::resolveRendezVousDataType and reinterprets the object
# by that type in NeNetRendezVousStatObject::convertStat, ignoring the className
# we send. Type mismatch corrupts (convertStat reads bytes as a Quazal::String).
#
# type enum: 0=Unknown 1=UInt24 2=UInt8 3=UInt32 4=UInt16 5=Float 6=String.
# ids not listed = Unknown(0). UInt24Statistic (3-byte) handled by write/parse
# (statistics._append_value).
RENDEZVOUS_READ_CLASS = {
    0x01: "StringStatistic",
    0x02: "UInt32Statistic",
    0x03: "UInt24Statistic",
    0x04: "FloatStatistic",
    0x05: "UInt24Statistic",
    0x06: "UInt24Statistic",
    0x07: "FloatStatistic",
    0x08: "FloatStatistic",
    0x09: "FloatStatistic",
    0x0A: "UInt16Statistic",
    0x0B: "UInt8Statistic",
    0x0C: "UInt16Statistic",
    0x0D: "UInt8Statistic",
    0x0E: "UInt8Statistic",
    0x0F: "UInt32Statistic",
    0x10: "StringStatistic",
    0x11: "StringStatistic",
    0x15: "UInt16Statistic",
    0x16: "UInt16Statistic",
    0x17: "UInt32Statistic",
    0x18: "UInt24Statistic",
    0x19: "FloatStatistic",
    0x1A: "UInt24Statistic",
    0x1B: "UInt24Statistic",
    0x1C: "FloatStatistic",
    0x1D: "FloatStatistic",
    0x1E: "FloatStatistic",
    0x1F: "UInt16Statistic",
    0x20: "UInt8Statistic",
    0x21: "UInt16Statistic",
    0x29: "UInt16Statistic",
    0x2A: "UInt16Statistic",
    0x33: "UInt32Statistic",
    0x34: "UInt8Statistic",
    0x36: "UInt16Statistic",
    0x37: "UInt16Statistic",
    0x38: "UInt16Statistic",
    0x39: "UInt8Statistic",
    0x3A: "UInt8Statistic",
    0x3D: "UInt16Statistic",
    0x3E: "UInt16Statistic",
    0x3F: "UInt16Statistic",
    0x40: "UInt32Statistic",
    0x47: "UInt32Statistic",
    0x48: "UInt24Statistic",
    0x49: "UInt8Statistic",
    0x4A: "UInt8Statistic",
    0x4B: "FloatStatistic",
    0x4C: "FloatStatistic",
    0x4D: "FloatStatistic",
    0x4E: "UInt16Statistic",
    0x4F: "UInt8Statistic",
    0x50: "UInt8Statistic",
    0x51: "UInt8Statistic",
    0x52: "UInt8Statistic",
    0x53: "UInt8Statistic",
    0x54: "StringStatistic",
    0x55: "StringStatistic",
    0x56: "StringStatistic",
    0x57: "StringStatistic",
    0x5B: "UInt8Statistic",
    0x5C: "UInt8Statistic",
    0x5D: "UInt24Statistic",
    0x65: "UInt16Statistic",
    0x66: "UInt24Statistic",
    0x67: "UInt24Statistic",
    0x68: "UInt8Statistic",
    0x69: "UInt8Statistic",
    0x6A: "UInt16Statistic",
    0x6B: "UInt16Statistic",
    0x6C: "UInt16Statistic",
    0x6D: "UInt16Statistic",
    0x6E: "UInt8Statistic",
    0x6F: "UInt8Statistic",
    0x70: "UInt16Statistic",
    0x71: "UInt16Statistic",
    0x72: "UInt24Statistic",
    0x73: "UInt24Statistic",
    0x74: "UInt16Statistic",
    0x75: "UInt16Statistic",
    0x76: "UInt8Statistic",
    0x77: "UInt8Statistic",
    0x78: "UInt16Statistic",
    0x79: "UInt8Statistic",
    0x7A: "UInt8Statistic",
    0x7B: "UInt8Statistic",
}
# 0xCA..0xF7 are all UInt8 in the table (the boolean flag block).
for _sid in range(0xCA, 0xF8):
    RENDEZVOUS_READ_CLASS.setdefault(_sid, "UInt8Statistic")


def read_class_for(stat_id, default="UInt32Statistic"):
    """Concrete AnyData class the client expects when reading this stat id back
    (from resolveRendezVousDataType). Use for read responses, not class_for."""
    return RENDEZVOUS_READ_CLASS.get(stat_id, default)
