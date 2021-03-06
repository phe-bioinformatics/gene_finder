#!/usr/bin/env python
import logging
from subprocess import call
import os,sys,inspect,re,subprocess

module_folder_paths = ["modules"]
for module_folder_path in module_folder_paths:
	module_folder = os.path.realpath(os.path.abspath(os.path.join(os.path.split(inspect.getfile( inspect.currentframe() ))[0],module_folder_path)))
	if module_folder not in sys.path:
		sys.path.insert(1, module_folder)

import gf_utils
# from utility_functions import *
## import log_writer



"""
Function
Index reference file using bowtie2-build in the same directory of the reference fasta file
Input:
- fasta_file[str]:full path to reference fasta file
- logger: python class logging.Logger created with stderr and stdout paths
"""
def index_reference(fasta_file,logger):
    gf_utils.info_header(logger, "index reference file using bowtie2")
    process = subprocess.Popen(['bowtie2-build', '-f', fasta_file, fasta_file], stderr=subprocess.PIPE, stdout=subprocess.PIPE)
    process.wait()
    gf_utils.log_process(logger, process, log_error_to = "bowtie2: reference indexing successfully completed")
    gf_utils.info_header(logger,'bowtie2: reference indexing successfully completed')

"""
Function
Create SAMtools index file (.fai) in the same directory of the reference fasta
.fai file = tab delimited file with gene_ids and sequence lengths
Input:
- fasta_file[str]: full path to reference fasta file
- logger: python class logging.Logger created with stderr and stdout paths
"""
def samtools_faidx(fasta_file,logger):
    process = subprocess.Popen(['samtools', 'faidx', fasta_file], stderr=subprocess.PIPE, stdout=subprocess.PIPE)
    process.wait()
    gf_utils.log_process(logger, process, log_error_to = "info")
    fai_index = fasta_file + '.fai'
    if os.path.getsize(fai_index) > 0:
        gf_utils.info_header(logger,'samtootls faidx sucsessfully created')
    else:
        gf_utils.info_header(logger,'samtootls faidx output is empty, check reference fasta format')
        sys.exit(1)

"""
Function
run bowtie2 with default_options =['-q','--very-sensitive-local','--no-unal','-a'] and generate SAM file in output/tmp (tmp/"sample_id".sam)

NB: bowtie_options can be modified using argument --bopt (-bowtie_options) with new options provided as a list##
Input:
- fasta_file[str]: full path_to reference_fasta
- forward_fastq[str]: full path to paired_fastq_forward
- reverse_fastq[str]: full path to paired_fastq_reverse
- outdir[str]: full path to output_directory
- workflow_name[str]: species_workflow (eg. staphylococcus-aureus-typing)
- version[str]: verion number (eg. 1-0-0)
- prefix[str]: (eg. molis id) used for labelling all_outputs
- bowtie_options[str]:list bowtie_options (if not default)
- logger: python class logging.Logger created with stderr and stdout paths
"""
def run_bowtie_on_indices(fasta_file,forward_fastq,reverse_fastq,outdir,workflow_name,version,prefix,bowtie_options,logger):
    sam_output = outdir + "/tmp/" + prefix + '.sam'
    gf_utils.info_header(logger,'running bowtie command')
    bowtie_options_combined = ' '.join(bowtie_options) # bowtie_option is a list need to be joined by space before assigned to the command line
    process = subprocess.Popen(['bowtie2','-1', forward_fastq, '-2', reverse_fastq,'-x',fasta_file,'-S', sam_output, bowtie_options_combined],stderr=subprocess.PIPE, stdout=subprocess.PIPE)
    process.wait()
    gf_utils.info_header(logger,'SAM file successfully created')

"""
Function
Deduce 256 from the second column to unset secondary alignment. Reads with 250 bit scrore are not reported when using Samtools pileup
A modified sam.mod file is created in the same directory of the original sam file
Input:
- path_sam_folder[str]: full path to the sam folder
- prefix[str]:(eg. molis id) used for labelling all_outputs
- logger: python class logging.Logger created with stderr and stdout paths

Return
sam.mod file in the same directoruy of the original .sam file

"""
def modify_bowtie_sam(path_sam_folder,prefix,logger):
    path_sam_file = path_sam_folder + "/" + prefix + ".sam" # prefix = sample_id (eg. molis id)
    with open(path_sam_file) as sam, open(path_sam_file + '.mod', 'w') as sam_mod:
        for line in sam:
            if not line.startswith('@'):
                fields = line.split('\t')
                flag = int(fields[1])
                flag = (flag - 256) if (flag > 256) else flag
                sam_mod.write('\t'.join([fields[0], str(flag)] + fields[2:]))
            else:
                sam_mod.write(line)
    gf_utils.info_header(logger,'SAM file successfully mofified to unset secondary alignment')

"""
Function
Description: Run SAMtools and generate BAM, sort and index BAM files
Input:
-path_to_tmp_file[str]: path to the tmp folder (containing the .sam .sam.mod files)
-fasta_file[str]:path_to reference_fasta
-prefix[str]: sample id (eg. molis id)
-logger: python class logging.Logger created with stderr and stdout paths

Returns
generate BAM, sorted BAM and pileup in tmp_file

"""
def run_samtools_bam(path_to_tmp_file,fasta_file,prefix,logger):
    sam_output = path_to_tmp_file + "/"+ prefix + ".sam"
    bam_output = path_to_tmp_file + "/" + prefix + ".bam"
    bam_sorted_output = path_to_tmp_file + "/" + prefix + ".sorted"
    bam_sorted_index_output = bam_sorted_output + ".bam"
    pileup_output = path_to_tmp_file + "/" + prefix + '.pileup'

    gf_utils.info_header(logger,'converting .sam to .bam')
    process = subprocess.Popen(['samtools', 'view', '-b', '-o', bam_output, '-q', '1', '-S', sam_output + '.mod'],stderr=subprocess.PIPE, stdout=subprocess.PIPE)
    process.wait()
    gf_utils.log_process(logger, process, log_error_to = "info")

    gf_utils.info_header(logger,'samtools sorting .bam file')
    process = subprocess.Popen(['samtools', 'sort', bam_output, bam_sorted_output],stderr=subprocess.PIPE, stdout=subprocess.PIPE)
    process.wait()
    gf_utils.log_process(logger, process, log_error_to = "info")

    gf_utils.info_header(logger,'samtools indexing .bam file')
    process = subprocess.Popen(['samtools', 'index', bam_sorted_index_output],stderr=subprocess.PIPE, stdout=subprocess.PIPE)
    process.wait()
    gf_utils.log_process(logger, process, log_error_to = "info")

    gf_utils.info_header(logger,'generating mpileup file')
    gf_utils.info_header(logger,' '.join(map(str,['samtools', 'mpileup', '-A', '-B', '-f', fasta_file, bam_sorted_index_output])))
    with open(pileup_output, 'w') as sam_pileup:
        process = subprocess.Popen(['samtools', 'mpileup', '-A', '-B', '-f', fasta_file, bam_sorted_index_output], stderr=subprocess.PIPE, stdout=subprocess.PIPE)
        for x in process.stdout:
            sam_pileup.write(x)
        process.wait()
        gf_utils.log_process(logger, process, log_error_to = "couldn't generate mpileup file")

"""
Function
wrapper script with all steps needed to generate mpileup: generating .sam, .bam and .mpileup files
Input:
- fasta_file[str]:full path to reference fasta file
- forward_fastq[str]: full path to the forward fastq file
- reverse_fastq[str]: full path to the reverse fastq file
- outdir[str]:path to output_directory
- workflow_name[str]:species_workflow (eg. staphylococcus-aureus-typing)
- version[str]:verion number (eg. 1-0-0)
- ids[str]: sample id (eg. molis id)
- bowtie_options[list]: bowtie_options, default:['-q', '--very-sensitive-local', '--no-unal', '-a']
- logger: python class logging.Logger created with stderr and stdout paths

"""
def generate_mpileup(path_to_tmp_file,fasta_file,forward_fastq,reverse_fastq,outdir,workflow_name,version,ids,bowtie_options,logger):
    run_bowtie_on_indices(fasta_file,forward_fastq,reverse_fastq,outdir,workflow_name,version,ids,bowtie_options,logger)
    modify_bowtie_sam(path_to_tmp_file,ids,logger)
    run_samtools_bam(path_to_tmp_file,fasta_file,ids,logger)
