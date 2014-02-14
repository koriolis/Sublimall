# -*- coding:utf-8 -*-
import os
import shutil
import sublime
import subprocess
from . import blacklist
from .logger import logger
from .utils import get_7za_bin
from .utils import generate_temp_filename


class Archiver(object):
    """
    Archiver using external executable
    """
    def __init__(self):
        """
        Stores sublime packages paths
        """
        self.directory_list = {
            sublime.packages_path(): '',
            sublime.installed_packages_path(): '.sublime-package'
        }
        self.packages_bak_path = '%s.bak' % sublime.packages_path()
        self.installed_packages_bak_path = '%s.bak' % sublime.installed_packages_path()

    def _safe_rmtree(self, directory):
        """
        Safely removes a directory
        """
        if os.path.exists(directory):
            shutil.rmtree(directory, ignore_errors=True)

    def _safe_copy(self, source, destination):
        if not os.path.exists(destination):
            shutil.copytree(source, destination, symlinks=True)

    def _safe_move(self, source, destination):
        """
        Safely moves the source to the destination
        """
        if os.path.exists(source):
            shutil.move(source, destination)

    def _is_os_nt(self):
        """
        Returns whether current os is Windows or not
        """
        return os.name == 'nt'

    def _get_7za_executable(self):
        """
        Returns absolute 7za executable path
        """
        zip_bin = get_7za_bin()
        if zip_bin is None:
            logger.error("Couldn't find 7za binary")
            raise Exception("Couldn't find 7za binary")
        return zip_bin

    def _get_output_dir(self):
        """
        Returns the default output directory
        """
        # Assuming Packages and Installed Packages are in the same directory !
        return os.path.abspath(os.path.join(list(self.directory_list)[0], os.path.pardir))

    def _run_executable(self, command, password=None, **kwargs):
        """
        Runs 7z executable with arguments
        """
        assert command in ['a', 'x']

        # Pack archive
        if command == 'a':
            assert 'output_filename' in kwargs
            command_args = [self._get_7za_executable(), command, '-tzip', '-y']
            if password is not None:
                command_args.append('-p%s' % password)
            if 'excluded_dirs' in kwargs:
                command_args.extend(['-x!%s*' % excluded_dir for excluded_dir in kwargs['excluded_dirs']])
            command_args.append(kwargs['output_filename'])
            command_args.extend(self.directory_list.keys())
        # Unpack archive
        elif command == 'x':
            assert all(k in kwargs for k in ['input_file', 'output_dir'])
            command_args = [self._get_7za_executable(), command, '-tzip', '-y', '-o%s' % kwargs['output_dir']]
            if password is not None:
                command_args.append('-p%s' % password)
            command_args.append(kwargs['input_file'])

        # Run command
        startupinfo = None
        if self._is_os_nt():
            startupinfo = subprocess.STARTUPINFO()
            startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
        process = subprocess.Popen(command_args, startupinfo=startupinfo)
        exitcode = process.wait()

        return exitcode

    def _excludes_from_package_control(self):
        """
        Returns a list of files / directories that Package Control handles
        """
        pc_settings = sublime.load_settings('Package Control.sublime-settings')
        installed_packages = pc_settings.get('installed_packages', [])
        return [
            '%s%s' % (os.path.join(os.path.split(directory)[1], package_name), suffix)
            for package_name in installed_packages if package_name.lower() != 'package control'
            for directory, suffix in self.directory_list.items()
        ]

    def move_packages_to_backup_dirs(self):
        """
        Moves packages directories to backups
        """
        self.remove_backup_dirs()

        logger.info('Move %s to %s' % (
            sublime.installed_packages_path(), self.installed_packages_bak_path))
        self._safe_copy(
            sublime.installed_packages_path(), self.installed_packages_bak_path)
        logger.info('Move %s to %s' % (
            sublime.packages_path(), self.packages_bak_path))
        self._safe_copy(
            sublime.packages_path(), self.packages_bak_path)

    def remove_backup_dirs(self):
        """
        Removes packages backups directories
        """
        for directory in [self.packages_bak_path, self.installed_packages_bak_path]:
            logger.info('Remove old backup dir: %s' % directory)
            self._safe_rmtree(directory)

    def pack_packages(
            self,
            password=None,
            backup=False,
            exclude_from_package_control=True,
            **kwargs):
        """
        Compresses Packages and Installed Packages
        """
        excluded_dirs = kwargs.get('excluded_dirs', [])
        packages_root_path = os.path.basename(sublime.packages_path())
        installed_packages_root_path = os.path.basename(sublime.installed_packages_path())

        # Append blacklisted Packages to excluded dirs
        for package in blacklist.packages:
            excluded_dirs.append(os.path.join(packages_root_path, package))

        # Append blacklisted Installed Packages to excluded dirs
        for package in blacklist.installed_packages:
            excluded_dirs.append(os.path.join(installed_packages_root_path, package))

        # Add Package Control excludes
        if exclude_from_package_control and not backup:
            excluded_dirs.extend(self._excludes_from_package_control())

        logger.info('Excluded dirs: %s' % excluded_dirs)
        kwargs['excluded_dirs'] = excluded_dirs

        # Generate a temporary output filename if necessary
        if 'output_filename' not in kwargs:
            kwargs['output_filename'] = generate_temp_filename()
        self._run_executable('a', password=password, **kwargs)
        return kwargs['output_filename']

    def unpack_packages(self, input_file, output_dir=None, password=None):
        """
        Uncompresses Packages and Installed Packages
        """
        if output_dir is None:
            output_dir = self._get_output_dir()
        logger.info('Extract in %s directory' % output_dir)
        self._run_executable(
            'x', password=password, input_file=input_file, output_dir=output_dir)
