"""
NewsFeed protocol (100) for DiRT 2 PS3.

Methods:
  1 getIndividualNewsFeed
  2 getMultipleNewsFeeds -> qVector<NewsItem>   (used by the FE)

Fetched per-friend on online rendezvous refresh (NeNetNewsReader::startServerRead),
rendered on ScreenNews / ScreenInitialNews (heading -> title glyph, body -> body glyph).
"""

import logging

from quazal.common import Structure
from quazal.rmc import ProtocolHandler

logger = logging.getLogger(__name__)


class NewsItem(Structure):
    """_DDL_NewsItem::Extract wire order. Attributes interpolate into a localized
    template; with literal heading/body we send zero attributes."""

    def __init__(
        self,
        item_id=1,
        owning_principal=0,
        expires=0,
        heading="",
        body="",
        scribble="",
        attributes=0,
    ):
        self.item_id = item_id  # u64
        self.owning_principal = owning_principal  # u32
        self.expires = expires  # u64 DateTime, 0 = never
        self.heading = heading  # String, title glyph
        self.body = body  # String, body glyph
        self.scribble = scribble  # String, unused
        self.attributes = attributes  # u32 qVector<AnyObjectHolder> count

    def save(self, out, version):
        out.u64(self.item_id)
        out.u32(self.owning_principal)
        out.u64(self.expires)
        out.string(self.heading)
        out.string(self.body)
        out.string(self.scribble)
        out.u32(self.attributes)


class NewsFeedService(ProtocolHandler):
    """Protocol 100 - NewsFeed (NewsFeedProtocolClient)."""

    PROTOCOL_ID = 100

    async def handle(self, client, method_id, input_stream, output_stream):
        # Empty feed. To publish, add NewsItem(heading=..., body=...) entries.
        news = []
        logger.info(
            f"NewsFeed(proto100) method {method_id} "
            f"({input_stream.remaining()} body bytes) -> {len(news)} items"
        )
        output_stream.u32(len(news))  # qVector<NewsItem> count
        for item in news:
            output_stream.add(item)
