from celery import shared_task

from allianceauth.services.tasks import QueueOnce

from . import snapshot


# once: a click on "Recalculate" while the scheduled run is still going would
# only compute the same thing twice
@shared_task(base=QueueOnce, once={"graceful": True})
def update_snapshot():
    """Recalculate the markers and connections from the data of the other apps."""
    snapshot.update()
