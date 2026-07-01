import sys
sys.path.insert(0, "/app")

import logging

from services.cache.l2_store import top_queries, set as l2_set, invalidate_version
from services.kiotel_dashboard_step_guide.tool import handle_kiotel_rag

logger = logging.getLogger(__name__)


def warm(portal_id: str, old_version: str, new_version: str, top_k: int = 50) -> dict:
    queries = top_queries(portal_id, old_version, limit=top_k)
    invalidate_version(portal_id, old_version)

    warmed = 0
    failed = 0

    for item in queries:
        try:
            result = handle_kiotel_rag({"question": item["query"]})
            if not result.get("found"):
                failed += 1
                continue

            l2_set(
                query=item["query"],
                answer=result["answer"],
                portal_id=portal_id,
                frontend_version=new_version,
                intent=item["intent"],
            )
            warmed += 1
        except Exception:
            logger.error("cache warm failed for query %r", item.get("query"), exc_info=True)
            failed += 1

    return {"warmed": warmed, "failed": failed, "old_version": old_version, "new_version": new_version}