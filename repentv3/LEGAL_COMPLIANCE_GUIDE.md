# Legal Compliance Guide for Discord Bot Verification

## Overview

This guide provides instructions for using the Privacy Policy and Terms of Service documents included with Repent for Discord bot verification and legal compliance.

## Document Locations

- **Privacy Policy:** `PRIVACY_POLICY.md`
- **Terms of Service:** `TERMS_OF_SERVICE.md`
- **Compliance Guide:** `LEGAL_COMPLIANCE_GUIDE.md`

## Discord Bot Verification Requirements

Discord requires the following for bot verification:

### 1. Privacy Policy
- ✅ Clearly describes what data is collected
- ✅ Explains how data is used and stored
- ✅ Specifies data retention periods
- ✅ Details user rights and data deletion procedures
- ✅ Includes contact information for privacy inquiries
- ✅ Discloses data collection in Discord Developer Portal

### 2. Terms of Service
- ✅ Outlines acceptable use policy
- ✅ Describes user responsibilities
- ✅ Includes limitation of liability clauses
- ✅ Specifies termination conditions
- ✅ Complies with Discord's Terms of Service
- ✅ Is publicly accessible

### 3. Data Collection Disclosure
Your Discord Developer Portal must accurately disclose:
- ✅ Guilds (server data)
- ✅ Guild Members (user data)
- ✅ Messages (content for moderation)
- ✅ Channels (channel data)
- ✅ Roles (role data)
- ✅ Audit Logs (security monitoring)
- ✅ Voice States (if used)

## Required Updates Before Use

### 1. Personal Information
Replace the placeholder information in both documents:

**In both PRIVACY_POLICY.md and TERMS_OF_SERVICE.md, replace:**
```
- **Discord:** [Your Discord Username]
- **Email:** [Your Email Address]
- **GitHub:** [Your GitHub Repository]
- **Website:** [Your Website URL]
```

**With your actual information:**
```
- **Discord:** YourName#1234
- **Email:** your.email@example.com
- **GitHub:** https://github.com/yourusername/repent
- **Website:** https://yourbot.com
```

### 2. Jurisdiction Information
In TERMS_OF_SERVICE.md, Section 11.1, replace:
```
These Terms shall be governed by and construed in accordance with the laws of [Your Jurisdiction]
```

With your actual jurisdiction:
```
These Terms shall be governed by and construed in accordance with the laws of California, United States
```

### 3. Arbitration Service
In TERMS_OF_SERVICE.md, Section 11.2, replace:
```
- Arbitration shall be conducted by [Arbitration Service]
- The arbitration shall take place in [Your City]
```

With actual information (or remove arbitration section if not needed):
```
- Arbitration shall be conducted by the American Arbitration Association
- The arbitration shall take place in San Francisco, California
```

## Making Documents Publicly Accessible

### Option 1: Host on Your Website
1. Upload the documents to your website
2. Ensure they are publicly accessible
3. Add links to your Discord server or bot information page

### Option 2: GitHub Repository
1. Upload to your bot's GitHub repository
2. Ensure the repository is public
3. Add a README with links to the legal documents

### Option 3: Discord Bot Commands
Consider adding commands to display the documents:
```
/privacy - Shows the privacy policy
/tos - Shows the terms of service
/legal - Shows both documents
```

### Option 4: External Hosting Services
- GitHub Pages
- GitBook
- Notion (public page)
- Google Docs (public link)

## Discord Developer Portal Configuration

### 1. Privacy Policy URL
Add your privacy policy URL to:
- Discord Developer Portal → Your Application → Bot → Privacy Policy URL

### 2. Terms of Service URL
Add your terms of service URL to:
- Discord Developer Portal → Your Application → Bot → Terms of Service URL

### 3. Data Collection Disclosure
Ensure your Discord Developer Portal accurately reflects the data scopes your bot uses:
- `bot` scope with required permissions
- Specific intent reasons for each data type
- Clear explanations of why each data type is needed

## International Compliance

### GDPR (European Union)
- The Privacy Policy includes GDPR compliance provisions
- Users can request data access, deletion, and portability
- Contact information must be responsive to GDPR requests
- Data processing must have a legal basis (user consent, legitimate interest, etc.)

### CCPA (California)
- The Privacy Policy includes CCPA compliance provisions
- California residents have specific rights regarding their data
- Clear opt-out mechanisms must be provided
- Do not sell personal information (your bot doesn't)

### Children's Privacy
- COPPA compliance for users under 13
- Your bot is not directed at children under 13
- No knowingly collecting data from children under 13

## Ongoing Compliance

### Regular Updates
- Review and update legal documents annually
- Update when adding new features that collect data
- Update when Discord policies change
- Update when laws change in your jurisdiction

### Document Versioning
- Maintain version history of legal documents
- Clearly indicate when documents were last updated
- Notify users of significant changes

### User Communication
- Announce significant policy changes through your bot
- Provide reasonable notice before major changes
- Allow users to opt-out of new data collection
- Make it easy for users to delete their data

## Bot Commands for Legal Compliance

Consider adding these commands to help with compliance:

```python
@bot.tree.command(name="privacy")
async def privacy(interaction: discord.Interaction):
    """Display the privacy policy"""
    embed = discord.Embed(
        title="Privacy Policy",
        description="Our full privacy policy is available at: [YOUR_URL]",
        color=0x4488FF
    )
    embed.add_field(name="Data Collection", value="We collect server and user data for security purposes only.")
    embed.add_field(name="Your Rights", value="You can request data deletion by removing the bot from your server.")
    embed.set_footer(text="Last updated: June 11, 2026")
    await interaction.response.send_message(embed=embed)

@bot.tree.command(name="tos")
async def tos(interaction: discord.Interaction):
    """Display the terms of service"""
    embed = discord.Embed(
        title="Terms of Service",
        description="Our full terms of service are available at: [YOUR_URL]",
        color=0x4488FF
    )
    embed.add_field(name="Acceptable Use", value="Use the bot only for security and moderation purposes.")
    embed.add_field(name="Prohibited Uses", value="Do not use the bot to harass other users or violate Discord's ToS.")
    embed.set_footer(text="Last updated: June 11, 2026")
    await interaction.response.send_message(embed=embed)

@bot.tree.command(name="delete_data")
async def delete_data(interaction: discord.Interaction):
    """Request deletion of server data"""
    if not interaction.user.guild_permissions.administrator:
        return await interaction.response.send_message("Only administrators can request data deletion.", ephemeral=True)
    
    # Implement data deletion logic
    await interaction.response.send_message("Data deletion request received. Your data will be deleted within 7 days.")
```

## Verification Checklist

Before submitting for Discord bot verification, ensure:

- [ ] Privacy Policy is publicly accessible via URL
- [ ] Terms of Service is publicly accessible via URL
- [ ] Privacy Policy URL is set in Discord Developer Portal
- [ ] Terms of Service URL is set in Discord Developer Portal
- [ ] Data collection is accurately disclosed in Discord Developer Portal
- [ ] Privacy Policy includes all required sections
- [ ] Terms of Service includes required legal provisions
- [ ] Contact information is accurate and responsive
- [ ] Documents are updated with your actual information
- [ ] Bot commands provide links to legal documents
- [ ] Data deletion process is clear and functional
- [ ] You have mechanisms to handle GDPR/CCPA requests

## Additional Resources

- [Discord Developer Documentation - Verification](https://discord.com/developers/docs/verification)
- [Discord Developer Policy](https://discord.com/developers/docs/policy)
- [GDPR Compliance Guide](https://gdpr.eu/)
- [CCPA Compliance Guide](https://oag.ca.gov/privacy/ccpa)

## Legal Disclaimer

*This guide is for informational purposes only and does not constitute legal advice. Laws and regulations vary by jurisdiction and change over time. For specific legal advice regarding your bot and compliance requirements, consult with a qualified attorney in your jurisdiction.*

---

**Last Updated:** June 11, 2026