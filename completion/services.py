"""
Runtime service for communicating completion information to the xblock system.
"""

from __future__ import unicode_literals

from django.conf import settings

from .models import BlockCompletion
from . import waffle


class CompletionService(object):
    """
    Service for handling completions for a user within a course.

    Exposes

    * self.completion_tracking_enabled() -> bool
    * self.visual_progress_enabled() -> bool
    * self.get_completions(candidates)
    * self.vertical_is_complete(vertical_item)

    Constructor takes a user object and course_key as arguments.
    """
    def __init__(self, user, course_key):
        self._user = user
        self._course_key = course_key

    def completion_tracking_enabled(self):
        """
        Exposes ENABLE_COMPLETION_TRACKING waffle switch to XModule runtime

        Return value:

            bool -> True if completion tracking is enabled.
        """
        return waffle.waffle().is_enabled(waffle.ENABLE_COMPLETION_TRACKING)

    def visual_progress_enabled(self):
        """
        Exposes VISUAL_PROGRESS_ENABLED waffle switch to XModule runtime

        Return value:

            bool -> True if VISUAL_PROGRESS flag is enabled.
        """
        return waffle.visual_progress_enabled(self._course_key)

    def get_completions(self, candidates):
        """
        Given an iterable collection of block_keys in the course, returns a
        mapping of the block_keys to the present completion values of their
        associated blocks.

        If a completion is not found for a given block in the current course,
        0.0 is returned.  The service does not attempt to verify that the block
        exists within the course.

        Parameters:

            candidates: collection of BlockKeys within the current course.
            Note: Usage keys may not have the course run filled in for old mongo courses.
            This method checks for completion records against a set of BlockKey candidates with the course run
            filled in from self._course_key.

        Return value:

            dict[BlockKey] -> float: Mapping blocks to their completion value.
        """
        queryset = BlockCompletion.user_course_completion_queryset(self._user, self._course_key).filter(
            block_key__in=candidates
        )
        completions = BlockCompletion.completion_by_block_key(queryset)
        candidates_with_runs = [candidate.replace(course_key=self._course_key) for candidate in candidates]
        for candidate in candidates_with_runs:
            if candidate not in completions:
                completions[candidate] = 0.0
        return completions

    def vertical_is_complete(self, item):
        """
        Calculates and returns whether a particular vertical is complete.
        The logic in this method is temporary, and will go away once the
        completion API is able to store a first-order notion of completeness
        for parent blocks (right now it just stores completion for leaves-
        problems, HTML, video, etc.).
        """
        if item.location.block_type != 'vertical':
            raise ValueError('The passed in xblock is not a vertical type!')

        if not self.completion_tracking_enabled():
            return None

        # this is temporary local logic and will be removed when the whole course tree is included in completion
        child_locations = [
            child.location for child in item.get_children() if child.location.block_type != 'discussion'
        ]
        completions = self.get_completions(child_locations)
        for child_location in child_locations:
            if completions[child_location] < 1.0:
                return False
        return True

    def get_completion_by_viewing_delay_ms(self):
        """
        Do not mark blocks complete-by-viewing until they have been visible for
        the returned amount of time, in milliseconds.  Defaults to 5000.
        """
        return getattr(settings, 'COMPLETION_BY_VIEWING_DELAY_MS', 5000)
