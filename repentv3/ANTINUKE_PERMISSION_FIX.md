# Antinuke Permission Hierarchy Fix

## Problem Identified

The antinuke system was failing to punish attackers even though Repent had Administrator permissions and was at the top of the role hierarchy. The error message was:
```
"I tried to punish AntiRaid#0357 (1510854558929125416) for timeout but I lack permission"
```

## Root Cause

The original code in `cogs/antinuke.py` and `utils/multi_layer_defense.py` did not check Discord's role hierarchy before attempting punishment actions. In Discord:
- You cannot ban/kick/timeout users who have roles equal to or higher than your bot's top role
- Attempting to do so results in a `discord.Forbidden` error
- The bot was catching this exception but not handling it gracefully

## Fixes Implemented

### 1. Base Antinuke (`cogs/antinuke.py`)

**Enhanced `_apply_punishment` method:**
- Added role hierarchy check before attempting punishment
- Checks if target is server owner (cannot be punished)
- Checks if target's highest role >= bot's highest role
- Added alternative punishment fallback: if ban/kick/timeout fails due to hierarchy, tries "strip" instead
- Added detailed error logging with specific Forbidden exception handling
- Added informative embed notifications to owner when punishment fails

**New `_create_permission_denied_embed` method:**
- Creates detailed embed showing:
  - Target user and reason
  - Attempted punishment
  - Bot role position
  - User's top role position
  - Specific reason for permission denial

### 2. Multi-Layer Defense System (`utils/multi_layer_defense.py`)

**Enhanced `_execute_action` method in Layer5_ResponseExecution:**
- Added role hierarchy check before punitive actions
- Checks server owner status
- Checks role position comparison for: TIMEOUT, STRIP_PERMISSIONS, KICK, BAN, HARD_BAN
- Returns False when punishment cannot be executed
- Added proper error logging

### 3. Permission Logic

**Role Hierarchy Rules Implemented:**
```python
# Can punish if: user.highest_role.position < bot.top_role.position
# Cannot punish if: user.highest_role.position >= bot.top_role.position
# Cannot punish: server owner (regardless of roles)
```

**Alternative Punishment Fallback:**
- If ban/kick/timeout fails due to role hierarchy → try strip permissions
- Strip permissions only removes roles that are lower than bot's top role
- This provides some mitigation even when full punishment isn't possible

## Testing Recommendations

### To test the fix:

1. **Ensure Repent is at the top of the role hierarchy**
   - Move Repent's role above all other roles except the owner's personal role
   - Give Repent Administrator permissions

2. **Test with a user who has lower roles**
   - Create a test user with roles below Repent
   - Have them perform nuke actions
   - Verify that Repent successfully punishes them

3. **Test with a user who has equal/higher roles**
   - Create a test user with roles equal to or above Repent
   - Have them perform nuke actions
   - Verify that Repent logs the permission denial and attempts alternative punishment

4. **Check logs for detailed information**
   - Monitor `logs/error.log` for permission errors
   - Monitor `logs/security.log` for antinuke triggers
   - Look for detailed role hierarchy information in logs

## Important Notes

### Role Hierarchy in Discord

1. **Bot Position:** The bot's role must be higher than the roles of users you want to punish
2. **Owner Exception:** The server owner cannot be punished by anyone
3. **Managed Roles:** Integration/Bot roles cannot be removed
4. **Everyone Role:** The @everyone role is at position 0 and doesn't count as a "role" for hierarchy

### Troubleshooting If Issues Persist

1. **Check Repent's role position:**
   - Go to Server Settings → Roles
   - Drag Repent's role above all user roles (but below your personal admin role if you have one)

2. **Verify Administrator permission:**
   - Go to Server Settings → Roles → Repent's role
   - Ensure "Administrator" is enabled

3. **Check whitelist:**
   - Make sure the nuker is not whitelisted
   - Use `/whitelist list` to check whitelist status
   - Use `/whitelist remove @user` if they are whitelisted

4. **Verify antinuke is enabled:**
   - Use `/antinuke status` to check if antinuke is enabled
   - Use `/antinuke enable` if it's disabled

5. **Check thresholds:**
   - Use `/config threshold` to see current thresholds
   - Ensure thresholds are appropriate for your server size

## Files Modified

1. `cogs/antinuke.py` - Enhanced punishment logic with role hierarchy checks
2. `utils/multi_layer_defense.py` - Added role hierarchy checks to Layer5
3. `cogs/antinuke_advanced.py` - Inherits fixes from base antinuke

## Additional Improvements

The fix also includes:
- Better error logging with specific exception types
- Detailed owner notifications with embeds
- Alternative punishment strategies when primary punishment fails
- Clear distinction between different types of permission failures
- Graceful degradation when full punishment isn't possible

## Deployment

1. Restart the bot to load the updated code
2. Verify the bot starts successfully
3. Test with a controlled nuke scenario
4. Monitor logs to confirm punishments are working correctly

## Expected Behavior After Fix

✅ **Successful Punishment:** When bot can punish based on role hierarchy
✅ **Alternative Punishment:** When primary punishment fails due to hierarchy, tries strip
✅ **Detailed Logging:** All permission failures are logged with specific reasons
✅ **Owner Notification:** Owner gets detailed embed when punishment fails
✅ **No Silent Failures:** All permission issues are explicitly handled and reported