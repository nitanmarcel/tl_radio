import sys

import setuptools

if sys.version_info[0] < 3 or sys.version_info[1] < 7:
    sys.exit("Python versions lower than 3.7 are not supported! Please update to at least python 3.6. Exiting!")

with open("requirements.txt") as reqs:
    install_requires = reqs.read().splitlines()

setuptools.setup(
    name="tl_radio",
    version="0.0.5",
    url="https://github.com/nitanmarcel/tl_radio",

    author="Marcel Alexandru Nitan",
    author_email="nitan.marcel@gamil.com",

    description="Telegram UserBot to play and stream audio to telegram group chat using YoutubeDl and TgCalls.",
    long_description=open("README.md").read(),
    long_description_content_type="text/markdown",

    packages=setuptools.find_packages(),
    install_requires=install_requires,
    python_requires="~=3.7",

    classifiers=[
        "Development Status :: 4 - Beta",
        "License :: OSI Approved :: GNU General Public License v3 (GPLv3)",
        "Topic :: Communications :: Chat",
        "Framework :: AsyncIO",
        "Programming Language :: Python",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.7",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.9",
    ],
    package_data={"tl_radio": ["example_config.yaml"]}
)
