"""
Management command to extract student module data for LabXchange's blocks.
"""
import csv
import urllib

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError
from django.db.models import Prefetch

from opaque_keys import InvalidKeyError
from opaque_keys.edx.keys import UsageKey

from lms.djangoapps.courseware.models import StudentModule

User = get_user_model()


class Command(BaseCommand):
    """
    Dumps the student.username, course_id, module_state_key (aka block_id) and state (JSON) in CSV format.

    EXAMPLE USAGE:

    ./manage.py lms export_student_module_data --block-ids input.txt --output output.csv
        Queries for blocks matching IDs in the given input.txt file (one per line).

    ./manage.py lms export_student_module_data --block-ids input.txt --from-date 2020-01-01 --output output.csv
        Queries the courseware_studentmodule table for rows whose block IDs start with LabXchange's prefixes,
        starting from Jan 2020, when LabXchange was launched.

    ./manage.py lms export_student_module_data --dry-run --block-ids input.txt --from-date 2020-01-01
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
            "-o",
            "--output",
            type=str,
            default=None,
            help="Path/Name of the file to write the output into.",
        )

        parser.add_argument(
            '-b', '--block-ids',
            metavar='FILENAME|URL',
            help='File containing block/module IDs to export, one per line.',
        )

        parser.add_argument(
            '-f', '--from-date',
            metavar='YYYY-MM-DD',
            help='Include data created after this date.',
        )

        parser.add_argument(
            '-t', '--to-date',
            metavar='YYYY-MM-DD',
            help='Include data created before this date.',
        )

        parser.add_argument(
            '-s', '--batch-size',
            type=int,
            metavar='500',
            help='Number of block IDs to fetch per query.',
        )

    def _read_block_ids(self, filename):
        """
        Reads and returns a unique list of block IDs contained in filename.

        Raises CommandError if:
        * unable to read filename
        * no valid UsageKey values are found in filename
        """
        if not filename:
            raise CommandError('--block-ids FILENAME required')

        # Is filename a URL?
        parsed = urllib.parse.urlparse(filename)
        if parsed.scheme:
            try:
                input_file = urllib.request.urlopen(filename)
            except urllib.error.URLError as err:
                raise CommandError(f'Unable to read URL {filename}, {err}') from err
        else:
            try:
                input_file = open(filename)
            except IOError as err:
                raise CommandError(f'Unable to read --block-ids {filename}, {err}') from err

        block_ids = set()
        for line in input_file:
            # Decode any binary data
            block_id = line.strip()
            if not isinstance(block_id, str):
                block_id = block_id.decode('utf-8')

            # Add only a valid UsageKey to the list
            try:
                usage_key = UsageKey.from_string(block_id)
                block_ids.add(usage_key)
            except InvalidKeyError:
                self.stderr.write(f'Invalid key "{block_id}": SKIPPED')
        input_file.close()

        if not block_ids:
            raise CommandError(f'No valid block IDs found in {filename}')

        return block_ids

    def handle(self, *args, **options):
        """
        Prepare and run the query against StudentModule using the given options.
        """
        queryset = StudentModule.objects

        # Filter by block_ids (in batches)
        block_ids = self._read_block_ids(options.get('block_ids'))
        batch_size = options['batch_size'] or len(block_ids)
        num_batches = len(list(chunks(block_ids, batch_size)))

        # Filter by date range
        if options.get('from_date'):
            queryset = queryset.exclude(created__lt=options['from_date'])
        if options.get('to_date'):
            queryset = queryset.exclude(created__gt=options['to_date'])

        # Open the output file/stream
        if options["output"]:
            output = open(options["output"], "w")
        else:
            output = self.stdout

        # 0. EXPLAIN the query, or run it?
        if options['dry_run']:
            # Explain only the first batch
            modules = next(chunked_filter(queryset, 'module_state_key__in', block_ids, batch_size))
            output.write(modules.explain(format='json'))
            return

        # 1. Gather total count
        total = 0
        for modules in chunked_filter(queryset, 'module_state_key__in', block_ids, batch_size):
            total += modules.count()
        if not total:
            self.stderr.write("No records found.")
            return

        # Ensure we're prefetching the student's username
        queryset = queryset.prefetch_related(
            Prefetch('student', User.objects.only('username'), to_attr='student_username')
        )

        # 2. Fetch and output the data
        columns = ['student_username', 'course_id', 'module_state_key', 'state', 'created', 'modified']
        writer = csv.writer(output)
        writer.writerow(columns)
        fetched = 0
        percent = 0
        batch = 0
        self.stdout.write(f"Fetching {total} records... (in {num_batches} batches)", ending='\r')
        for modules in chunked_filter(queryset, 'module_state_key__in', block_ids, batch_size):
            batch += 1

            for module in modules:
                writer.writerow([getattr(module, col, 'None') for col in columns])
                fetched += 1
                percent = int(100 * fetched / total)
                self.stdout.write(
                    f"Fetched {fetched} / {total} records (batch {batch} / {num_batches})... {percent}%",
                    ending='\r',
                )

        self.stdout.write(
            f"Fetched {fetched} / {total} records (batch {batch} / {num_batches})... {percent}%",
        )


def chunks(items, chunk_size):
    """
    Yields the values from items in chunks of size chunk_size
    """
    items = list(items)
    return (items[i:i + chunk_size] for i in range(0, len(items), chunk_size))

def chunked_filter(queryset, chunk_field, items, chunk_size=500):
    """
    Generates querysets filtered on chunk_field=items, where the items are divided into chunk_size batches.
    """
    for chunk in chunks(items, chunk_size):
        yield queryset.filter(**{chunk_field: chunk})
