/* Copyright (C) 2013, 2014 Canonical Ltd.
 * Author: Colin Watson <cjwatson@ubuntu.com>
 *
 * This program is free software: you can redistribute it and/or modify
 * it under the terms of the GNU General Public License as published by
 * the Free Software Foundation; version 3 of the License.
 *
 * This program is distributed in the hope that it will be useful,
 * but WITHOUT ANY WARRANTY; without even the implied warranty of
 * MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
 * GNU General Public License for more details.
 *
 * You should have received a copy of the GNU General Public License
 * along with this program.  If not, see <http://www.gnu.org/licenses/>.
 */

/* Things that should be in posix.vapi, but aren't.  */

[CCode (cprefix = "", lower_case_cprefix = "")]
namespace PosixExtra {
	/* https://bugzilla.gnome.org/show_bug.cgi?id=725149 */
	[Compact]
	[CCode (cname = "struct group", cheader_filename = "grp.h")]
	public class Group {
		public string gr_name;
		public string gr_passwd;
		public Posix.gid_t gr_gid;
		[CCode (array_length = false, array_null_terminated = true)]
		public string[] gr_mem;
	}
	[CCode (cheader_filename = "grp.h")]
	public unowned Group? getgrent ();

	[CCode (cheader_filename = "unistd.h")]
	public int getresgid (out Posix.gid_t rgid, out Posix.gid_t egid, out Posix.gid_t sgid);
	[CCode (cheader_filename = "unistd.h")]
	public int getresuid (out Posix.uid_t ruid, out Posix.uid_t euid, out Posix.uid_t suid);
	[CCode (cheader_filename = "unistd.h")]
	public int setegid (Posix.gid_t egid);
	[CCode (cheader_filename = "unistd.h")]
	public int seteuid (Posix.uid_t euid);
	[CCode (cheader_filename = "sys/types.h,grp.h,unistd.h")]
	public int setgroups (size_t size, [CCode (array_length = false)] Posix.gid_t[] list);
	[CCode (cheader_filename = "unistd.h")]
	public int setresgid (Posix.gid_t rgid, Posix.gid_t egid, Posix.gid_t sgid);
	[CCode (cheader_filename = "unistd.h")]
	public int setresuid (Posix.uid_t ruid, Posix.uid_t euid, Posix.uid_t suid);
}
