# Security Policy

## Supported Versions

| Version | Supported          |
| ------- | ------------------ |
| 1.0.x   | :white_check_mark: |

## Reporting a Vulnerability

If you discover a security vulnerability, please report it by emailing [your-email@example.com].

Please include:
- Description of the vulnerability
- Steps to reproduce
- Potential impact
- Suggested fix (if any)

## Security Best Practices

### API Keys and Credentials

- **Never commit `.env` files** to version control
- Use `.env.example` as a template with placeholder values
- Rotate API keys regularly
- Use environment-specific credentials

### Docker Deployment

- Keep Docker images updated
- Use non-root users where possible
- Scan images for vulnerabilities: `docker scan scripts-to-audiobook`

### Data Protection

- Generated audio files may contain sensitive content
- Ensure proper access controls on `data/` directory
- Regular backups recommended

---

# 安全策略

## 支持的版本

| 版本 | 支持状态 |
| ------- | ------------------ |
| 1.0.x | :white_check_mark: |

## 报告漏洞

如果您发现安全漏洞，请通过邮件报告到 [your-email@example.com]。

请包含：
- 漏洞描述
- 复现步骤
- 潜在影响
- 建议修复方案（如有）

## 安全最佳实践

### API 密钥和凭证

- **永远不要将 `.env` 文件提交**到版本控制
- 使用 `.env.example` 作为带有占位值的模板
- 定期轮换 API 密钥
- 使用环境特定的凭证

### Docker 部署

- 保持 Docker 镜像更新
- 尽可能使用非 root 用户
- 扫描镜像漏洞：`docker scan scripts-to-audiobook`

### 数据保护

- 生成的音频文件可能包含敏感内容
- 确保对 `data/` 目录进行适当的访问控制
- 建议定期备份
