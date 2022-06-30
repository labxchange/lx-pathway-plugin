"""
Management command to extract student module data for LabXchange's blocks.
"""
import csv

from cursor_pagination import CursorPaginator
from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand
from django.db.models import Prefetch, Q
from lms.djangoapps.courseware.models import StudentModule

User = get_user_model()


class Command(BaseCommand):
    """
    Dumps the student.username, course_id, module_state_key (aka block_id) and state (JSON) in CSV format to stdout.

    EXAMPLE USAGE:

    ./manage.py lms export_student_module_data > output.csv
        Queries the courseware_studenmodule table for rows whose block IDs start with LabXchange's prefixes.

    ./manage.py lms export_student_module_data --block-prefix "lb:SomeOrg,lb:AnotherOrg" > output.csv
        Queries for blocks matching "lb:SomeOrg" or "lb:AnotherOrg", rather than the default list of block ID prefixes.

    ./manage.py lms export_student_module_data --dry-run
        Runs an EXPLAIN command on the proposed query to show cost and complexity, but does not run the query itself.
        ref https://dev.mysql.com/doc/refman/5.7/en/explain-output.html
    """

    def add_arguments(self, parser):
        """
        Add optional arguments to the command.
        """
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Run EXPLAIN on the query and display output in JSON format',
        )

        parser.add_argument(
            '-b', '--block-prefix',
            type=lambda s: list(s.split(',')),
            default=[
                'lb:LabXchange:',
                'lb:HarvardX:',
                'lb:SDGAcademyX:',
                'lx-pb:',
            ],
            help='Request a different (comma-delimited) list of block prefixes than the default.',
        )

    def handle(self, *args, **options):
        """
        Prepare and run the query against StudentModule using the given options.
        """
        # Assemble an OR filter with the requested block prefixes
        prefix_q = Q()
        for prefix in options['block_prefix']:
            prefix_q |= Q(module_state_key__startswith=prefix)

        modules = StudentModule.objects.filter(prefix_q).prefetch_related(
            Prefetch('student', User.objects.only('username'), to_attr='student_username')
        )

        if options['dry_run']:
            self.stdout.write(modules.explain(format='json'))
            return

        columns = ['student_username', 'course_id', 'module_state_key', 'state']
        writer = csv.writer(self.stdout)
        writer.writerow(columns)
        for module in chunked_queryset_iterator(modules):
            writer.writerow([getattr(module, col, 'None') for col in columns])


# Ref https://blog.labdigital.nl/working-with-huge-data-sets-in-django-169453bca049
def chunked_queryset_iterator(queryset, size=1000, *, ordering=('id',)):
    """Split a queryset into chunks.

    This can be used instead of ``queryset.iterator()``,
    so ``.prefetch_related()`` also works.

    .. note::
    The ordering must uniquely identify the object,
    and be in the same order (ASC/DESC).
    """
    pager = CursorPaginator(queryset, ordering)
    after = None

    while True:
        page = pager.page(after=after, first=size)
        if page:
            yield from page.items
        else:
            return

        if not page.has_next:
            break

        # take last item, next page starts after this.
        after = pager.cursor(instance=page[-1])
