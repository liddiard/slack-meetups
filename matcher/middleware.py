import hmac
import hashlib
import logging

from django.http import JsonResponse

from meetups import settings


logger = logging.getLogger(__name__)


class VerifySlackRequest:
    """verify that a request came from Slack
    https://api.slack.com/docs/verifying-requests-from-slack
    """

    # using old-style middleware to allow us to use a per-view decorator
    # (we only want this verification on Slack views, not places like admin)
    # see: https://docs.djangoproject.com/en/2.2/ref/utils/#django.utils.decorators.decorator_from_middleware
    # https://docs.djangoproject.com/en/1.9/topics/http/middleware/#process_request

    def process_request(self, request):
        # implementation partially from:
        # https://janikarhunen.fi/verify-slack-requests-in-aws-lambda-and-python

        timestamp = request.headers["X-Slack-Request-Timestamp"]
        slack_signature = request.headers["X-Slack-Signature"]
        # make the signing secret a bytestring
        signing_secret = bytes(settings.SLACK_SIGNING_SECRET, "utf-8")
        request_body = request.body.decode('utf-8')

        # form the base string as stated in the Slack API docs. We need to
        # make a bytestring.
        base_string = f"v0:{timestamp}:{request_body}".encode("utf-8")

        # create a new HMAC "signature", and return the string presentation
        request_signature = 'v0=' + hmac.new(signing_secret, base_string,
            hashlib.sha256).hexdigest()

        # compare the the Slack-provided signature to ours. If they are equal,
        # the request should continue
        if hmac.compare_digest(request_signature, slack_signature):
            pass
        else:
            logger.warning("Request verification failed. Base string: "
                f"{base_string} Slack signature: {slack_signature}, Request "
                f"signature: {request_signature}")
            return JsonResponse(status=403, 
                data={"error": "request verification failed"})
