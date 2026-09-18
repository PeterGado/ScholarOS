class InvalidStorageConfigurationError(RuntimeError):
    """Raised when `storage_backend` is set to "s3" but the required S3 configuration (at
    minimum `s3_bucket`) is missing - fails fast at dependency-resolution time rather than
    surfacing as a confusing downstream boto3 error on the first upload. Mirrors `app.auth.
    exceptions.InvalidAuthConfigurationError`'s own fail-fast precedent.
    """
