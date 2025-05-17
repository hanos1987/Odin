import discord
from discord.ext import commands
import json
import logging
import os
import asyncio

# Setup logging
logger = logging.getLogger(__name__)

# File to store role configurations
ROLE_CONFIG_FILE = "role_configs.json"

# Your Discord user ID (replace with your actual user ID)
ALLOWED_ADMIN_ID = 123456789012345678  # Replace with your Discord user ID

class RoleManager(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.role_configs = self.load_role_configs()
        logger.info("Initializing RoleManager cog")
        self._register_commands()

    def _register_commands(self):
        """Register this cog's commands in functions.json."""
        logger.info("Starting command registration for RoleManager")
        commands_to_register = {
            "role_manager": "Manages roles (create/remove/modify) via DM (admin-only). Usage: role_manager",
            "assign_role": "Assigns a low-level role to yourself. Usage: assign_role <role_name>",
            "view_roles": "Views your current roles. Usage: view_roles",
            "view_role_configs": "Views all role configurations (admin-only). Usage: view_role_configs",
            "role_manager_help": "Shows the functionality of the RoleManager cog. Usage: role_manager_help"
        }
        try:
            try:
                with open('functions.json', 'r') as f:
                    data = json.load(f)
                logger.info("Successfully read functions.json")
            except FileNotFoundError:
                data = {"cogs": {}, "bot_commands": {}}
                logger.warning("functions.json not found, creating new structure")

            if "cogs" not in data:
                data["cogs"] = {}
            data["cogs"]["role_manager"] = {"commands": commands_to_register}
            with open('functions.json', 'w') as f:
                json.dump(data, f, indent=4)
            logger.info("Successfully registered commands for RoleManager")
        except Exception as e:
            logger.error(f"Failed to register commands for RoleManager cog: {e}")

    # Load role configurations from file
    def load_role_configs(self):
        if os.path.exists(ROLE_CONFIG_FILE):
            with open(ROLE_CONFIG_FILE, 'r') as f:
                return json.load(f)
        return {"roles": {}}

    # Save role configurations to file
    def save_role_configs(self):
        with open(ROLE_CONFIG_FILE, 'w') as f:
            json.dump(self.role_configs, f, indent=2)

    # Check if the user is an admin
    def check_admin(self):
        async def predicate(ctx):
            if ctx.author.id != ALLOWED_ADMIN_ID:
                await ctx.send("Sorry, you are not authorized to use this command.")
                return False
            return True
        return commands.check(predicate)

    # Check if the user has @everyone role (all users have this by default)
    def check_everyone(self):
        async def predicate(ctx):
            everyone_role = discord.utils.get(ctx.guild.roles, name="@everyone")
            if everyone_role not in ctx.author.roles:
                await ctx.send("You need the @everyone role to use this command.")
                return False
            return True
        return commands.check(predicate)

    @commands.command(name="role_manager")
    @commands.check(check_admin)
    async def role_manager(self, ctx):
        """Manages roles (create/remove/modify) via DM (admin-only). Usage: role_manager"""
        try:
            await ctx.author.send("Welcome to Role Manager! Please choose an action: `create`, `remove`, or `modify`.")
            await ctx.send("I’ve sent you a DM to manage roles.")
        except discord.Forbidden:
            await ctx.send("I couldn’t DM you. Please enable DMs from server members.")
            return

        def check(msg):
            return msg.author == ctx.author and isinstance(msg.channel, discord.DMChannel)

        try:
            # Step 1: Get the action
            action_msg = await self.bot.wait_for('message', check=check, timeout=300)
            action = action_msg.content.strip().lower()

            if action not in ["create", "remove", "modify"]:
                await ctx.author.send("Invalid action. Please choose `create`, `remove`, or `modify`.")
                return

            if action == "create":
                await self.create_role(ctx)
            elif action == "remove":
                await self.remove_role(ctx)
            elif action == "modify":
                await self.modify_role(ctx)

        except asyncio.TimeoutError:
            await ctx.author.send("Timed out waiting for your reply. Please use `#role_manager` again.")

    async def create_role(self, ctx):
        """Handles role creation via DM."""
        def check(msg):
            return msg.author == ctx.author and isinstance(msg.channel, discord.DMChannel)

        try:
            # Step 2: Get role name
            await ctx.author.send("Please enter the name of the role to create:")
            name_msg = await self.bot.wait_for('message', check=check, timeout=300)
            role_name = name_msg.content.strip()
            if not role_name:
                await ctx.author.send("Role name cannot be empty. Please try again.")
                return

            # Check if role already exists
            existing_role = discord.utils.get(ctx.guild.roles, name=role_name)
            if existing_role:
                await ctx.author.send(f"Role `{role_name}` already exists. Use `modify` to edit it or `remove` to delete it.")
                return

            # Step 3: Determine if the role is low-level
            await ctx.author.send("Should this role be low-level (assignable by anyone with @everyone)? Reply with `yes` or `no`.")
            level_msg = await self.bot.wait_for('message', check=check, timeout=300)
            is_low_level = level_msg.content.strip().lower() == "yes"

            # Step 4: Prompt for permissions
            permissions = await self.prompt_permissions(ctx)

            # Step 5: Confirm role creation
            perms_summary = ", ".join([perm for perm, value in permissions.items() if value])
            await ctx.author.send(
                f"Here’s the role you want to create:\n"
                f"Name: `{role_name}`\n"
                f"Low-Level: `{is_low_level}`\n"
                f"Permissions: `{perms_summary or 'None'}`\n"
                f"Is this correct? Reply with `yes` to confirm or `no` to cancel."
            )
            confirmation_msg = await self.bot.wait_for('message', check=check, timeout=300)
            if confirmation_msg.content.strip().lower() != "yes":
                await ctx.author.send("Role creation cancelled.")
                return

            # Step 6: Create the role
            perms = discord.Permissions(**permissions)
            try:
                new_role = await ctx.guild.create_role(
                    name=role_name,
                    permissions=perms,
                    reason=f"Created by {ctx.author} via RoleManager"
                )
            except discord.Forbidden:
                await ctx.author.send("I don’t have permission to create roles. Please ensure I have the `Manage Roles` permission.")
                return

            # Step 7: Save role configuration
            self.role_configs["roles"][role_name] = {
                "id": new_role.id,
                "is_low_level": is_low_level,
                "permissions": permissions
            }
            self.save_role_configs()

            # Step 8: Manage role hierarchy (ensure new role is below bot’s highest role)
            bot_top_role = max([role for role in ctx.guild.me.roles], key=lambda r: r.position)
            if new_role.position > bot_top_role.position:
                await new_role.edit(position=bot_top_role.position - 1)

            await ctx.send(f"Role `{role_name}` created successfully!")

        except asyncio.TimeoutError:
            await ctx.author.send("Timed out waiting for your reply. Please use `#role_manager` again.")

    async def remove_role(self, ctx):
        """Handles role removal via DM."""
        def check(msg):
            return msg.author == ctx.author and isinstance(msg.channel, discord.DMChannel)

        try:
            # Step 2: Get role name
            await ctx.author.send("Please enter the name of the role to remove:")
            name_msg = await self.bot.wait_for('message', check=check, timeout=300)
            role_name = name_msg.content.strip()
            if not role_name:
                await ctx.author.send("Role name cannot be empty. Please try again.")
                return

            # Check if role exists
            role = discord.utils.get(ctx.guild.roles, name=role_name)
            if not role:
                await ctx.author.send(f"Role `{role_name}` does not exist.")
                return

            # Step 3: Confirm removal
            await ctx.author.send(
                f"Are you sure you want to remove the role `{role_name}`?\n"
                f"Reply with `yes` to confirm or `no` to cancel."
            )
            confirmation_msg = await self.bot.wait_for('message', check=check, timeout=300)
            if confirmation_msg.content.strip().lower() != "yes":
                await ctx.author.send("Role removal cancelled.")
                return

            # Step 4: Remove the role
            try:
                await role.delete(reason=f"Removed by {ctx.author} via RoleManager")
            except discord.Forbidden:
                await ctx.author.send("I don’t have permission to delete roles. Please ensure I have the `Manage Roles` permission.")
                return

            # Step 5: Update role configurations
            if role_name in self.role_configs["roles"]:
                del self.role_configs["roles"][role_name]
                self.save_role_configs()

            await ctx.send(f"Role `{role_name}` removed successfully!")

        except asyncio.TimeoutError:
            await ctx.author.send("Timed out waiting for your reply. Please use `#role_manager` again.")

    async def modify_role(self, ctx):
        """Handles role modification via DM."""
        def check(msg):
            return msg.author == ctx.author and isinstance(msg.channel, discord.DMChannel)

        try:
            # Step 2: Get role name
            await ctx.author.send("Please enter the name of the role to modify:")
            name_msg = await self.bot.wait_for('message', check=check, timeout=300)
            role_name = name_msg.content.strip()
            if not role_name:
                await ctx.author.send("Role name cannot be empty. Please try again.")
                return

            # Check if role exists
            role = discord.utils.get(ctx.guild.roles, name=role_name)
            if not role:
                await ctx.author.send(f"Role `{role_name}` does not exist.")
                return

            # Step 3: Determine if the role should be low-level
            await ctx.author.send("Should this role be low-level (assignable by anyone with @everyone)? Reply with `yes` or `no`.")
            level_msg = await self.bot.wait_for('message', check=check, timeout=300)
            is_low_level = level_msg.content.strip().lower() == "yes"

            # Step 4: Prompt for permissions
            permissions = await self.prompt_permissions(ctx)

            # Step 5: Confirm modification
            perms_summary = ", ".join([perm for perm, value in permissions.items() if value])
            await ctx.author.send(
                f"Here’s the modified role configuration:\n"
                f"Name: `{role_name}`\n"
                f"Low-Level: `{is_low_level}`\n"
                f"Permissions: `{perms_summary or 'None'}`\n"
                f"Is this correct? Reply with `yes` to confirm or `no` to cancel."
            )
            confirmation_msg = await self.bot.wait_for('message', check=check, timeout=300)
            if confirmation_msg.content.strip().lower() != "yes":
                await ctx.author.send("Role modification cancelled.")
                return

            # Step 6: Modify the role
            perms = discord.Permissions(**permissions)
            try:
                await role.edit(
                    permissions=perms,
                    reason=f"Modified by {ctx.author} via RoleManager"
                )
            except discord.Forbidden:
                await ctx.author.send("I don’t have permission to modify roles. Please ensure I have the `Manage Roles` permission.")
                return

            # Step 7: Update role configurations
            self.role_configs["roles"][role_name] = {
                "id": role.id,
                "is_low_level": is_low_level,
                "permissions": permissions
            }
            self.save_role_configs()

            # Step 8: Manage role hierarchy
            bot_top_role = max([r for r in ctx.guild.me.roles], key=lambda r: r.position)
            if role.position > bot_top_role.position:
                await role.edit(position=bot_top_role.position - 1)

            await ctx.send(f"Role `{role_name}` modified successfully!")

        except asyncio.TimeoutError:
            await ctx.author.send("Timed out waiting for your reply. Please use `#role_manager` again.")

    async def prompt_permissions(self, ctx):
        """Prompts the user for permissions to enable/disable via DM."""
        def check(msg):
            return msg.author == ctx.author and isinstance(msg.channel, discord.DMChannel)

        # Define permissions to prompt for
        permission_options = [
            "manage_channels",
            "manage_roles",
            "kick_members",
            "ban_members",
            "manage_messages",
            "send_messages",
            "read_message_history",
            "add_reactions"
        ]
        permissions = {perm: False for perm in permission_options}

        await ctx.author.send(
            "Let’s set permissions for the role. For each permission, reply with `yes` to enable or `no` to disable."
        )

        for perm in permission_options:
            await ctx.author.send(f"Enable `{perm}` permission? (yes/no)")
            try:
                perm_msg = await self.bot.wait_for('message', check=check, timeout=300)
                enable = perm_msg.content.strip().lower() == "yes"
                permissions[perm] = enable
            except asyncio.TimeoutError:
                await ctx.author.send(f"Timed out waiting for `{perm}` permission. Defaulting to disabled.")
                permissions[perm] = False

        return permissions

    @commands.command(name="assign_role")
    @commands.check(check_everyone)
    async def assign_role(self, ctx, *, role_name: str):
        """Assigns a low-level role to yourself. Usage: assign_role <role_name>"""
        if role_name not in self.role_configs["roles"]:
            await ctx.send(f"Role `{role_name}` does not exist in the role configurations.")
            return

        role_config = self.role_configs["roles"][role_name]
        if not role_config["is_low_level"]:
            await ctx.send(f"Role `{role_name}` is not a low-level role and cannot be assigned using this command.")
            return

        role = discord.utils.get(ctx.guild.roles, id=role_config["id"])
        if not role:
            await ctx.send(f"Role `{role_name}` no longer exists in the server.")
            return

        if role in ctx.author.roles:
            await ctx.send(f"You already have the role `{role_name}`.")
            return

        try:
            await ctx.author.add_roles(role, reason="Assigned via RoleManager")
            await ctx.send(f"Assigned role `{role_name}` to you!")
        except discord.Forbidden:
            await ctx.send("I don’t have permission to assign roles. Please ensure I have the `Manage Roles` permission.")

    @commands.command(name="view_roles")
    async def view_roles(self, ctx):
        """Views your current roles. Usage: view_roles"""
        roles = [role.name for role in ctx.author.roles if role.name != "@everyone"]
        if not roles:
            await ctx.send("You have no roles other than @everyone.")
            return

        roles_list = "\n".join(roles)
        await ctx.send(f"**Your Roles**:\n```\n{roles_list}\n```")

    @commands.command(name="view_role_configs")
    @commands.check(check_admin)
    async def view_role_configs(self, ctx):
        """Views all role configurations (admin-only). Usage: view_role_configs"""
        if not self.role_configs["roles"]:
            await ctx.send("No roles have been configured.")
            return

        config_output = "Role Configurations:\n"
        for role_name, config in self.role_configs["roles"].items():
            perms = ", ".join([perm for perm, value in config["permissions"].items() if value]) or "None"
            config_output += (
                f"Role: `{role_name}`\n"
                f"ID: `{config['id']}`\n"
                f"Low-Level: `{config['is_low_level']}`\n"
                f"Permissions: `{perms}`\n\n"
            )

        if len(config_output) > 1900:
            parts = [config_output[i:i+1900] for i in range(0, len(config_output), 1900)]
            for i, part in enumerate(parts, 1):
                await ctx.send(f"**Role Configurations (Part {i}/{len(parts)})**:\n```\n{part}\n```")
        else:
            await ctx.send(f"**Role Configurations**:\n```\n{config_output}\n```")

    @commands.command(name="role_manager_help")
    async def role_manager_help(self, ctx):
        """Shows the functionality of the RoleManager cog. Usage: role_manager_help"""
        help_text = (
            "**RoleManager Cog Functionality**\n\n"
            "This cog allows role management on the server with the following commands:\n"
            "- `#role_manager`: Creates, removes, or modifies roles (admin-only). You’ll be prompted via DM to:\n"
            "  - Choose an action (create/remove/modify).\n"
            "  - Specify the role name.\n"
            "  - Set it as low-level (assignable by anyone) or admin-only.\n"
            "  - Configure permissions (e.g., manage channels, kick members).\n"
            "- `#assign_role <role_name>`: Assigns a low-level role to yourself (available to anyone with @everyone).\n"
            "- `#view_roles`: Shows your current roles.\n"
            "- `#view_role_configs`: Shows all role configurations (admin-only).\n"
            "- `#role_manager_help`: Displays this help message.\n\n"
            "Roles are managed to avoid overlaps/conflicts by adjusting their hierarchy. Admin-only roles require setup by the designated admin."
        )
        await ctx.send(help_text)

async def setup(bot):
    await bot.add_cog(RoleManager(bot))
