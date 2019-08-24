const request = require('superagent'),
  { RTMClient } = require('@slack/rtm-api');

// An access token (from your Slack app or custom integration - usually xoxb)
const token = process.env.SLACK_API_TOKEN,
  host = process.env.HOST || "http://localhost:8000";

if (!token) {
  throw new Error('Missing environment variable for SLACK_API_TOKEN');
}

// The client is initialized and then started to get an active connection to the platform
const rtm = new RTMClient(token);
rtm.start()
  .catch(console.error);

rtm.on('ready', () => {
  console.log('RTM proxy ready, forwarding requests to:', host);
});

// After the connection is open, your app will start receiving other events.
rtm.on('message', async (event) => {
  // The argument is the event as shown in the reference docs.
  // For example, https://api.slack.com/events/user_typing
  if (event.bot_id) {
    // ignore messages sent from the bot so it doesn't respond to itself
    return;
  }
  if (typeof event.channel !== 'string' || !event.channel.startsWith('D') ||
      event.user === 'USLACKBOT') {
    // ignore messages that are not direct messages – this allows us to add
    // the bot to channels and not have it respond to messages in the channel.
    // the goal of this is to allow the bot to work in private channels where
    // it needs to be a memeber of the channel in order to read the members
    // list. if a channel starts with a "D", it's a direct message. this
    // feature is not officially documented but seems reliable... see:
    // https://stackoverflow.com/a/42013042
    // Also ignore messages from Slackbot. Not sure how this happens, but 
    // sometimes our bot can get stuck in an infinite conversation loop w/
    // Slackbot, until it gets ratelimited 🙃
    return;
  }
  console.log('message received from Slack:', event);
  let response;
  try {
    response = await request.post(`${host}/slack/message/`)
      .send(event);
    console.log('response status received from server:', response.status);
  }
  catch (ex) {
    console.error('error sending request to server:', ex);
  }
})
