from django.core.management.base import BaseCommand, CommandError

from matcher.models import Pool, Round


class Command(BaseCommand):
    help = "Creates a round of matching, thereby asking participants of the"\
        "specified pools for their availability. Syntax: python3 manage.py "\
        "create_round <channel_ids> (separate channel_ids with spaces)"

    def add_arguments(self, parser):
        parser.add_argument('channel_ids', nargs='+', type=str)

    def handle(self, *args, **options):
        for channel_id in options['channel_ids']:
            try:
                pool = Pool.objects.get(channel_id=channel_id)
            except Pool.DoesNotExist:
                raise CommandError(f"Pool \"{channel_id}\" does not exist.")

            round = Round(pool=pool)
            round.save()

            self.stdout.write(
                self.style.SUCCESS(f"Successfully created round \"{round}\"")
            )