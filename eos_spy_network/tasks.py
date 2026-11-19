from celery import shared_task

from allianceauth.services.tasks import QueueOnce

from . import capital_sweep, progress, snapshot


# once: a click on "Recalculate" while the scheduled run is still going would
# only compute the same thing twice
@shared_task(base=QueueOnce, once={"graceful": True})
def update_snapshot():
    """Recalculate the markers and connections from the data of the other apps."""
    try:
        snapshot.update(progress.step)
    finally:
        # a failed run must not leave the pages polling until the entry expires
        progress.finished()


# once: a sweep walks every region and takes minutes; a second one would only ask ESI the same again
@shared_task(base=QueueOnce, once={"graceful": True})
def sweep_capital_contracts():
    """Look up the open public contracts of the Alliance's Corporations for the marker *Capital in contract*."""
    capital_sweep.sweep()
