# Security Specification

## Overview

This specification defines security measures for MyAI to ensure safe configuration management, secure tool integration, and protection of sensitive data. Security is built-in by design, not bolted on.

## Core Security Principles

1. **Least Privilege**: Request only necessary permissions
2. **Defense in Depth**: Multiple layers of security
3. **Secure by Default**: Safe defaults, opt-in for risky features
4. **Transparency**: Clear security indicators and warnings
5. **No Secrets in Configs**: Credentials stay in secure storage

## File System Security

### Directory Permissions
```python
# Secure directory creation
import os
import stat

def create_secure_directory(path: Path) -> None:
    """Create directory with secure permissions"""
    path.mkdir(mode=0o700, parents=True, exist_ok=True)
    
    # Verify permissions
    current = path.stat().st_mode & 0o777
    if current != 0o700:
        os.chmod(path, 0o700)

# Directory permission standards
DIRECTORY_PERMISSIONS = {
    '~/.myai': 0o700,                    # User only
    '~/.myai/config': 0o700,              # User only
    '~/.myai/agents/custom': 0o700,       # User only
    '~/.myai/backups': 0o700,             # User only
    '~/.myai/logs': 0o700,                # User only
    '.myai': 0o755,                       # Project dirs readable
}
```

### File Permissions
```python
# Secure file creation
def write_secure_file(path: Path, content: str, mode: int = 0o600) -> None:
    """Write file with secure permissions"""
    # Write with restricted permissions
    with open(path, 'w', opener=lambda p, f: os.open(p, f, mode)) as f:
        f.write(content)

# File permission standards
FILE_PERMISSIONS = {
    'config.json': 0o600,                 # User read/write only
    'credentials.json': 0o600,            # User read/write only
    '*.key': 0o600,                       # Private keys
    '*.pem': 0o600,                       # Certificates
    'agents/*.md': 0o644,                 # Readable agents
}
```

## Sensitive Data Protection

### Environment Variables
```python
class SecureConfig:
    """Handle sensitive configuration data"""
    
    SENSITIVE_KEYS = {
        'api_key', 'secret', 'token', 'password',
        'credential', 'private_key', 'auth'
    }
    
    def load_config(self, path: Path) -> dict:
        """Load config with environment variable expansion"""
        config = json.loads(path.read_text())
        return self._expand_env_vars(config)
    
    def _expand_env_vars(self, obj: Any) -> Any:
        """Recursively expand environment variables"""
        if isinstance(obj, str):
            # Check for env var pattern
            if obj.startswith('${') and obj.endswith('}'):
                var_name = obj[2:-1]
                default = None
                
                # Handle default values ${VAR:-default}
                if ':-' in var_name:
                    var_name, default = var_name.split(':-', 1)
                
                value = os.environ.get(var_name, default)
                if value is None:
                    raise ValueError(f"Required environment variable {var_name} not set")
                
                return value
        elif isinstance(obj, dict):
            return {k: self._expand_env_vars(v) for k, v in obj.items()}
        elif isinstance(obj, list):
            return [self._expand_env_vars(item) for item in obj]
        
        return obj
```

### Credential Storage
```python
class CredentialManager:
    """Secure credential management"""
    
    def __init__(self):
        self.keyring_available = self._check_keyring()
    
    def _check_keyring(self) -> bool:
        """Check if system keyring is available"""
        try:
            import keyring
            return True
        except ImportError:
            return False
    
    def store_credential(self, service: str, key: str, value: str) -> None:
        """Store credential securely"""
        if self.keyring_available:
            import keyring
            keyring.set_password(f"myai-{service}", key, value)
        else:
            # Fall back to environment variable
            typer.echo(f"⚠️  Keyring not available. Set environment variable: {key.upper()}")
    
    def get_credential(self, service: str, key: str) -> Optional[str]:
        """Retrieve credential"""
        if self.keyring_available:
            import keyring
            return keyring.get_password(f"myai-{service}", key)
        else:
            # Fall back to environment variable
            return os.environ.get(key.upper())
```

## Input Validation

### Path Validation
```python
class PathValidator:
    """Validate and sanitize file paths"""
    
    @staticmethod
    def validate_path(path: str, base_dir: Path) -> Path:
        """Validate path is within base directory"""
        # Resolve to absolute path
        abs_path = Path(path).resolve()
        base_abs = base_dir.resolve()
        
        # Check if path is within base directory
        try:
            abs_path.relative_to(base_abs)
        except ValueError:
            raise SecurityError(f"Path {path} is outside allowed directory")
        
        # Check for suspicious patterns
        path_str = str(abs_path)
        suspicious_patterns = [
            '..', '~', '$', '`', '|', ';', '&',
            '\n', '\r', '\x00'
        ]
        
        for pattern in suspicious_patterns:
            if pattern in path_str:
                raise SecurityError(f"Suspicious pattern '{pattern}' in path")
        
        return abs_path
```

### Configuration Validation
```python
class ConfigValidator:
    """Validate configuration data"""
    
    # Maximum sizes to prevent DoS
    MAX_CONFIG_SIZE = 10 * 1024 * 1024  # 10MB
    MAX_STRING_LENGTH = 10000
    MAX_ARRAY_LENGTH = 1000
    
    def validate_config(self, config: dict) -> None:
        """Validate configuration structure and content"""
        # Check size
        config_str = json.dumps(config)
        if len(config_str) > self.MAX_CONFIG_SIZE:
            raise ValidationError("Configuration too large")
        
        # Validate structure
        self._validate_structure(config)
        
        # Check for injection attempts
        self._check_injections(config)
    
    def _check_injections(self, obj: Any, path: str = "") -> None:
        """Check for potential injection attacks"""
        if isinstance(obj, str):
            # Check for script injection
            dangerous_patterns = [
                '<script', 'javascript:', 'onclick=',
                'onerror=', '../', '..\\', 
                '${', '$(', '`'
            ]
            
            for pattern in dangerous_patterns:
                if pattern in obj.lower():
                    raise SecurityError(f"Potential injection in {path}: {pattern}")
                    
        elif isinstance(obj, dict):
            for key, value in obj.items():
                self._check_injections(value, f"{path}.{key}")
        elif isinstance(obj, list):
            for i, item in enumerate(obj):
                self._check_injections(item, f"{path}[{i}]")
```

## Tool Integration Security

### Command Execution
```python
class SecureExecutor:
    """Secure command execution"""
    
    ALLOWED_COMMANDS = {
        'git': ['status', 'log', 'diff', 'add', 'commit'],
        'npm': ['install', 'run', 'test'],
        'python': ['-m', 'pip', 'install'],
    }
    
    def execute_command(self, command: List[str]) -> subprocess.CompletedProcess:
        """Execute command with restrictions"""
        if not command:
            raise ValueError("Empty command")
        
        # Check if command is allowed
        base_cmd = command[0]
        if base_cmd not in self.ALLOWED_COMMANDS:
            raise SecurityError(f"Command '{base_cmd}' not allowed")
        
        # Validate arguments
        if len(command) > 1:
            allowed_args = self.ALLOWED_COMMANDS[base_cmd]
            if allowed_args and command[1] not in allowed_args:
                raise SecurityError(f"Argument '{command[1]}' not allowed for {base_cmd}")
        
        # Execute with restrictions
        return subprocess.run(
            command,
            capture_output=True,
            text=True,
            timeout=30,  # 30 second timeout
            check=False,
            env=self._get_safe_env()
        )
    
    def _get_safe_env(self) -> dict:
        """Get sanitized environment"""
        safe_env = os.environ.copy()
        
        # Remove sensitive variables
        sensitive_vars = [
            'AWS_SECRET_ACCESS_KEY',
            'GITHUB_TOKEN',
            'NPM_TOKEN'
        ]
        
        for var in sensitive_vars:
            safe_env.pop(var, None)
        
        return safe_env
```

## Audit Logging

### Security Events
```python
class SecurityAuditor:
    """Log security-relevant events"""
    
    def __init__(self, log_dir: Path):
        self.log_file = log_dir / 'security.log'
        self.setup_logger()
    
    def log_event(self, event_type: str, details: dict) -> None:
        """Log security event"""
        event = {
            'timestamp': datetime.utcnow().isoformat(),
            'type': event_type,
            'user': os.getuser(),
            'pid': os.getpid(),
            **details
        }
        
        # Write to append-only log
        with open(self.log_file, 'a') as f:
            json.dump(event, f)
            f.write('\n')
    
    def log_config_change(self, path: str, action: str) -> None:
        """Log configuration changes"""
        self.log_event('config_change', {
            'path': path,
            'action': action,
            'hash': self._hash_file(path)
        })
    
    def log_failed_auth(self, service: str, reason: str) -> None:
        """Log authentication failures"""
        self.log_event('auth_failure', {
            'service': service,
            'reason': reason
        })
```

## Network Security

### HTTPS Enforcement
```python
class SecureHTTPClient:
    """Secure HTTP client with certificate validation"""
    
    def __init__(self):
        self.session = httpx.Client(
            verify=True,  # Verify SSL certificates
            follow_redirects=False,  # Don't auto-follow
            timeout=30.0
        )
    
    def get(self, url: str) -> httpx.Response:
        """Secure GET request"""
        # Validate URL
        parsed = urlparse(url)
        
        # Enforce HTTPS
        if parsed.scheme != 'https':
            raise SecurityError("Only HTTPS URLs allowed")
        
        # Check against allowlist
        if not self._is_allowed_host(parsed.hostname):
            raise SecurityError(f"Host {parsed.hostname} not allowed")
        
        return self.session.get(url)
    
    def _is_allowed_host(self, hostname: str) -> bool:
        """Check if host is allowed"""
        allowed_hosts = [
            'api.anthropic.com',
            'github.com',
            'raw.githubusercontent.com',
            'myai.dev',
            'agents.myai.dev'
        ]
        
        return hostname in allowed_hosts
```

## Enterprise Security

### Policy Enforcement
```json
{
  "security_policy": {
    "min_password_length": 12,
    "require_mfa": true,
    "allowed_tools": ["claude", "cursor"],
    "forbidden_commands": ["rm -rf", "format"],
    "audit_all_changes": true,
    "encryption_required": true
  }
}
```

### Compliance Features
```python
class ComplianceManager:
    """Manage compliance requirements"""
    
    def check_compliance(self, config: dict) -> List[str]:
        """Check configuration compliance"""
        violations = []
        
        # Check encryption
        if not config.get('security', {}).get('encryption_enabled'):
            violations.append("Encryption must be enabled")
        
        # Check audit logging
        if not config.get('security', {}).get('audit_enabled'):
            violations.append("Audit logging must be enabled")
        
        # Check tool restrictions
        allowed = config.get('security_policy', {}).get('allowed_tools', [])
        for tool in config.get('tools', {}):
            if tool not in allowed:
                violations.append(f"Tool '{tool}' not allowed by policy")
        
        return violations
```

## Security Best Practices

### For Users
1. **Use Environment Variables**: Store secrets in environment variables
2. **Regular Updates**: Keep MyAI updated for security patches
3. **Audit Logs**: Review security logs regularly
4. **Minimal Permissions**: Grant only necessary tool permissions
5. **Backup Encryption**: Encrypt sensitive backups

### For Developers
1. **Input Validation**: Validate all user input
2. **Secure Defaults**: Make secure choices default
3. **Fail Securely**: Errors should not expose sensitive info
4. **Regular Audits**: Security audit before releases
5. **Dependency Scanning**: Check for vulnerable dependencies