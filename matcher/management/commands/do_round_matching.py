from django.core.management.base import BaseCommand, CommandError

from matcher.models import Pool, Round
from matcher.admin import match


class Command(BaseCommand):
    help = "Make matches for the latest round in the specified pools."

    def add_arguments(self, parser):
        parser.add_argument('channel_ids', nargs='+', type=str)

    def handle(self, *args, **options):
        for channel_id in options['channel_ids']:
            try:
                pool = Pool.objects.get(channel_id=channel_id)
            except Pool.DoesNotExist:
                raise CommandError(f"Pool \"{channel_id}\" does not exist.")

            latest_round = Round.objects.filter(pool=pool).latest('end_date')
            if not latest_round:
                raise CommandError(f"No rounds exist for pool \"{channel_id}\".")
            
            self.stdout.write(
                f"Attempting to make matches for round \"{latest_round}\"…"
            )
            # may raise an error if there are an odd number of people in the
            # round and no one who can be excluded. intentionally allow this
            # error, if raised, to fail the command
            match(latest_round)

            self.stdout.write(
                self.style.SUCCESS(f"Successfully triggered matching for round \"{latest_round}\"")
            )