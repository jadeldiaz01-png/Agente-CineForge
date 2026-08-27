package training.governance

default allow := false

allow if {
  count(input.datasets) > 0
  every dataset in input.datasets {
    dataset.policy_decision == "ALLOWED"
    dataset.license != ""
    dataset.terms_reviewed == true
    dataset.robots_reviewed == true
    dataset.contains_personal_data != true
  }
  input.eval_passed == true
  input.model_card_ready == true
  input.human_approved == true
}

deny[msg] if {
  count(input.datasets) == 0
  msg := "no approved datasets are registered"
}

deny[msg] if {
  some dataset in input.datasets
  dataset.policy_decision != "ALLOWED"
  msg := sprintf("dataset %s is not allowed for training", [dataset.dataset_id])
}

deny[msg] if {
  input.human_approved != true
  msg := "human approval is required before production model rollout"
}

