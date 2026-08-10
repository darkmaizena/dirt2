from enum import IntEnum


class PrizeGroupWire(IntEnum):
    """PrizeGroup.m_groupType:
    1 = TOP_N    (group_size = N)
    2 = PERCENT  (group_size = percent)
    3 = ORDINAL  (group_size = position ordinal)
    """

    TOP_N = 1
    PERCENT = 2
    ORDINAL = 3


class RewardKind(IntEnum):
    MONEY = 1
    XP = 2
    STRING = 3


class FormatterStyle(IntEnum):
    eAsIs = 0
    eDistanceLong = 1
    eDistanceSmall = 2
    eRaceTime = 3
    eDeltaTime = 4
    eSpeed = 5
    eMoney = 6
    eOfflineXp = 7
    eOnlineXp = 8
    ePosition = 9
    eCarId = 10
    eTrackId = 11
    eInvalid = 12


class PrizeGroupType(IntEnum):
    eInvalid = 0
    eExactPosition = 1
    eWithinGroup = 2
    ePercentileValue = 3


class StatDataType(IntEnum):
    eStatDataTypeUnknown = 0
    eStatDataTypeUInt24 = 1
    eStatDataTypeUInt8 = 2
    eStatDataTypeUInt32 = 3
    eStatDataTypeString = 4
    eStatDataTypeUInt16 = 5
    eStatDataTypeFloat = 6
    eStatDataTypeMaximumValue = 7


class CompetitionType(IntEnum):
    TypeInvalid = -1
    TypeSingle = 0
    TypeQualify = 1
    TypeKnockout = 2
    TypePosition = 3
    TypeLapTime = 4
    TypeSplits = 5
    TypePersonalChallenge = 6
    TypeDirtGamesCompetition = 7
    TypeTotal = 8


class UnlockGroup(IntEnum):
    eUnlockGroupCashPrize = 0
    eUnlockGroupCodriver = 1
    eUnlockGroupDashboard = 2
    eUnlockGroupEvent = 3
    eUnlockGroupHorn = 4
    eUnlockGroupJingle = 5
    eUnlockGroupLocation = 6
    eUnlockGroupVehicle = 7
    eUnlockGroupVehicleGrade = 8
    eUnlockGroupVehicleLivery = 9
    eUnlockGroupRVRevealObject = 10
    eUnlockGroupMax = 11


class RaceHistoryFloat(IntEnum):
    distanceTravelled = 0
    distanceTravelledCareerOnly = 1
    distanceTravelledWithNoAchievements = 2
    fastestSpeed = 3
    longestSlide = 4
    longestDistanceOnTwoWheels = 5
    longestTimeOnTwoWheels = 6
    longestJump = 7
    highestJump = 8
    totalJumpLength = 9
    totalJumpHeight = 10
    totalDriftLength = 11
    timeOnTwoWheels = 12
    longestCrashFreeDistance = 13
    currentCrashFreeDistance = 14
    maxFloatValues = 15


class RaceHistoryInt(IntEnum):
    numDNFs = 0
    numWonSessions = 1
    numWonCompetitions = 2
    numWonEvents = 3
    numWonRankedSessions = 4
    numWonSessionsCareerOnly = 5
    numWonEventsCareerOnly = 6
    numCompletedSessionCareerOnly = 7
    numCompletedEventsCareerOnly = 8
    numStartedEvents = 9
    numFinishedSessions = 10
    numFinishedCompetitions = 11
    numFinishedEvents = 12
    numXGamesWon = 13
    numPodiumSessions = 14
    numPodiumCompetitions = 15
    numPodiumEvents = 16
    numLostSessions = 17
    numLostCompetitions = 18
    numLostEvents = 19
    playerXP = 20
    missionsXp = 21
    numTerminalDamages = 22
    numConsecutiveEvents = 23
    numInstantReplayViews = 24
    numInstantReplayJumpIns = 25
    numLapsRaced = 26
    numWonKnockouts = 27
    totalAccPositions = 28
    fastestSpeedVehicleId = 29
    mostRolls = 30
    totalRolls = 31
    totalSpins = 32
    numCleanSessions = 33
    numCleanSessionWins = 34
    numManualSessionWins = 35
    numResets = 36
    currentNumConsecutiveWins = 37
    currentNumConsecutiveNonPodiumFinishes = 38
    highestNumConsecutiveWins = 39
    totalSpinAndWinSessions = 40
    totalRollAndWinSessions = 41
    numSessionsWonBackOfPack = 42
    starLevelOfLastEvent = 43
    numRacesWonByOver1Lap = 44
    numRacesWonByOver1Split = 45
    gotTopSpeedInRace = 46
    gotFastestLapInRace = 47
    vehiclesOverTaken = 48
    numEventsWonAllCompetitions = 49
    fastSectorsInARow = 50
    numObjectsDamaged = 51
    numEventSinceLastGeneratedPersonalChallenge = 52
    numCompletedPersonalChallenges = 53
    numTournamentsParticipated = 54
    numWonCompetitionsWithCustomCar = 55
    maxIntValues = 56
