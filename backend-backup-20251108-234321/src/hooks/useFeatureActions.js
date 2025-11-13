import * as Calls from "../services/api/calls";
import * as Campaigns from "../services/api/campaigns";
import * as Messages from "../services/api/messages";
import * as Numbers from "../services/api/numbers";
import * as Analytics from "../services/api/analytics";

const map = {
  "api.calls.start": Calls.start,
  "api.calls.recordings": Calls.listRecordings,
  "api.messages.inbox": Messages.inbox,
  "api.messages.bulk": Messages.bulkSend,
  "api.messages.email": Messages.emailBlast,
  "api.campaigns.schedule": Campaigns.schedule,
  "api.campaigns.compliance": Campaigns.compliance,
  "api.numbers.buy": Numbers.buy,
  "api.numbers.assign": Numbers.assign,
  "api.analytics.voice": Analytics.voice,
  "api.analytics.messaging": Analytics.messaging,
};

export const useFeatureActions = () => ({
  trigger: async (action, payload) => (map[action] ? map[action](payload) : null),
});
