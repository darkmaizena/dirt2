from .content_sharing import ContentSharingService
from .news_feed import NewsFeedService
from .race_report import RaceReportService
from .secure_connection import SecureConnectionService
from .statistics import StatisticsService
from .ticket_granting import TicketGrantingService
from .tournament import TournamentService

AUTH_HANDLERS = [TicketGrantingService]
SECURE_HANDLERS = [
    SecureConnectionService,
    ContentSharingService,
    StatisticsService,
    NewsFeedService,
    RaceReportService,
    TournamentService,
]
