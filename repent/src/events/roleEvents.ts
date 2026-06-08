import { Role } from 'discord.js';
import { RoleProtection } from '../modules/RoleProtection';
import { PermissionEscalationProtection } from '../modules/PermissionEscalationProtection';
import { Logger } from '../utils/Logger';

const roleProtection = new RoleProtection();
const permProtection = new PermissionEscalationProtection();
const logger = Logger.getInstance();

export const roleEvents = {
  async handleCreate(role: Role): Promise<void> {
    try {
      await roleProtection.handleRoleCreate(role);
    } catch (error) {
      logger.error('Role create protection error', { error, roleId: role.id });
    }
  },

  async handleDelete(role: Role): Promise<void> {
    try {
      await roleProtection.handleRoleDelete(role);
    } catch (error) {
      logger.error('Role delete protection error', { error, roleId: role.id });
    }
  },

  async handleUpdate(oldRole: Role, newRole: Role): Promise<void> {
    try {
      await roleProtection.handleRoleUpdate(oldRole, newRole);
      await permProtection.handleRoleUpdate(oldRole, newRole);
    } catch (error) {
      logger.error('Role update protection error', { error, roleId: newRole.id });
    }
  },
};
