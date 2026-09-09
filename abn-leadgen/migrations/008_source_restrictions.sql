ALTER TABLE suppression_event DROP CONSTRAINT suppression_event_reason_check;
ALTER TABLE suppression_event ADD CONSTRAINT suppression_event_reason_check CHECK(reason IN (
 'unsubscribe','complaint','no_unsolicited_notice','cancellation','manual','disappearance','source_inactive'
));
