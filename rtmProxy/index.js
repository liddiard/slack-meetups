const request = require('superagent'),
  { RTMClient } = require('@slack/rtm-api');

// An access token (from your Slack app or custom integration - usually xoxb)
const token = process.env.SLACK_API_TOKEN,
  port = process.env.PORT || 8000;

// The client is initialized and then started to get an active connection to the platform
const rtm = new RTMClient(token);
rtm.start()
  .catch(console.error);

rtm.on('ready', () => {
  console.log('RTM proxy ready, forwarding requests to port', port);
});

// After the connection is open, your app will start receiving other events.
rtm.on('message', async (event) => {
  // The argument is the event as shown in the reference docs.
  // For example, https://api.slack.com/events/user_typing
  if (event.bot_id) {
    // ignore messages sent from the bot so it doesn't respond to itself
    return;
  }
  console.log('message received from Slack:', event);
  let response;
  try {
    response = await request.post(`http://localhost:${port}/slack/message/`)
      .send(event);
    console.log('response status received from server:', response.status);
  }
  catch (ex) {
    console.error('error sending request to server:', ex);
  }
})
