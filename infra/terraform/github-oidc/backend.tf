terraform {
  backend "s3" {
    bucket         = "azref-tfstate-230148048244"
    key            = "github-oidc/terraform.tfstate"
    region         = "eu-west-1"
    dynamodb_table = "azref-tfstate-lock"
    encrypt        = true
  }
}
