from setuptools import setup, find_packages

setup(
    name='nano-iaas',
    version='0.1.0',
    description='Nano-IaaS: Leitura de dados multi-cloud via terminal',
    author='Seu Nome',
    packages=find_packages(),
    install_requires=[
        'click>=8.0',
        'boto3>=1.26',
        'google-cloud-storage>=2.0',
        'azure-storage-blob>=12.0',
        'azure-identity>=1.0',
        'pandas>=1.5',
        'pyarrow>=10.0',
        'rich>=13.0',
        'pyyaml>=6.0',
        'pydantic>=2.0'
    ],
    entry_points={
        'console_scripts': [
            'nano-iaas=cli.main:cli',
        ],
    },
    python_requires='>=3.9',
)
