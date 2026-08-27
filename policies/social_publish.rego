package social.publish

default allow := false

allow if {
  input.publishing_enabled == true
  input.connected == true
  input.production_ready == true
  input.account_id != ""
  input.access_token_present == true
  input.video_qc_passed == true
  input.originality_reviewed == true
  input.human_approved == true
  input.idempotency_key != ""
  input.published_count_24h < input.daily_limit
  input.public_posting_audited == true
}

deny[msg] if {
  input.connected != true
  msg := sprintf("%s connector is not connected", [input.platform])
}

deny[msg] if {
  input.production_ready != true
  msg := sprintf("%s connector is not production ready", [input.platform])
}

deny[msg] if {
  input.human_approved != true
  msg := "human approval is required before publishing"
}

deny[msg] if {
  input.public_posting_audited != true
  msg := "platform audit/review is required for public posting"
}
