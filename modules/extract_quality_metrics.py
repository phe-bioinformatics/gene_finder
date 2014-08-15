#!/usr/bin/env python
import logging
from subprocess import call
import os,sys,inspect,re,subprocess
from itertools import groupby, count
from operator import itemgetter
from collections import Counter
from StringIO import StringIO
from lxml import etree
from Bio import SeqIO
from Bio.Align.Applications import ClustalwCommandline
from Bio.Seq import Seq
from Bio.SeqRecord import SeqRecord
from Bio import AlignIO

module_folder_paths = ["modules"]
for module_folder_path in module_folder_paths:
	module_folder = os.path.realpath(os.path.abspath(os.path.join(os.path.split(inspect.getfile( inspect.currentframe() ))[0],module_folder_path)))
	if module_folder not in sys.path:
		sys.path.insert(1, module_folder)
import utility_functions
import log_writer


def extract_coverage_in_section(numberlist,tolerance):
    def as_range(iterable):
        l = list(iterable)
        if len(l) > 1:
            return '{0}-{1}'.format(l[0], l[-1])
        else:
            return '{0}'.format(l[0])   
    sections = ';'.join(as_range(g) for _, g in groupby(numberlist, key=lambda n, c=count(): n-next(c)))
    covered_sections = []
    for slot in sections.split(';'):
        if re.findall(r'[-]',slot):
            if int(slot.split('-')[1]) - int(slot.split('-')[0]) > int(tolerance):
                covered_sections.append(slot)
    split_covered = [elem.split("-") for elem in covered_sections]
    missing_sections = []
    for n,k in enumerate([elem.split("-") for elem in covered_sections][:-1]):
        missing_sections.append(split_covered[n][1] + "-" + split_covered[n+1][0])
    return covered_sections,missing_sections

#Main function
def extract_quality_metrics(mpileup_info_dictionary):
    pileup_hash = {}
    for allele in mpileup_info_dictionary:
        print allele
        print mpileup_info_dictionary[allele]
        positions_infos = mpileup_info_dictionary[allele]['positions_infos']
        positions_with_accepted_depth = mpileup_info_dictionary[allele]['positions_accepted_depth']
        position_mismatchs = mpileup_info_dictionary[allele]['position_mismatchs']
        total_inserted_nuc = mpileup_info_dictionary[allele]['inserted_nuc']
        position_insertions = mpileup_info_dictionary[allele]['position_insertions']
        positions_mix = mpileup_info_dictionary[allele]['positions_mix']
        position_deletions = mpileup_info_dictionary[allele]['position_deletions']
        positions_indels_probabilities = mpileup_info_dictionary[allele]['positions_indels_probabilities']
        allele_length = mpileup_info_dictionary[allele]['allele_length']
        sequence_raw =  mpileup_info_dictionary[allele]['sequence_raw']   
        if len(positions_infos) != 0:
            if len(positions_with_accepted_depth) != 0:                
                positions_with_reads_count = dict([(x,positions_infos[x]) for x in positions_infos if positions_infos[x] != '$' and positions_infos[x] != '*'])
                max_depth =  max(positions_with_reads_count.values())
                positions_with_coverage = dict([(x,positions_with_accepted_depth[x]) for x in positions_with_accepted_depth if positions_with_accepted_depth[x] != '$'])
                min_depth = min(positions_with_accepted_depth.values())
                average_depth = round(float(sum(positions_with_reads_count.values()))/float(len(positions_with_reads_count.values())),2)
                ratio_coverage = round(float(len(positions_with_coverage)*100)/float(allele_length),1)
                homology = round(float(len(positions_with_coverage) - len(position_mismatchs) - sum(total_inserted_nuc))*100/float(allele_length),2)
                        
                target_biosequence_final = []           
                for key in sorted(sequence_raw.iterkeys()):
                    target_biosequence_final.append(sequence_raw[key]) 
                
                #######extracting predicted seq and split in contigs if part has no coverage###
                # input for extract_coverage_in_section list = (all_positions_with_coverage) and int = min length of contig to_consider
                coverage_distribution,missing_sections = extract_coverage_in_section(positions_with_coverage.keys(),20)
                contig_counter = 0
                predicted_contig = []
                large_indels_position_taken = []
                updated_coverage_distribution = []
                for region in coverage_distribution:                  
                    contig_counter += 1
                    pos_details = region.split('-')
                    pot_indels_per_contig = []
                    for pot_indel in positions_indels_probabilities.keys():
                        if int(pot_indel) > int(pos_details[0]) and int(pot_indel) < int(pos_details[1]):
                            pot_indels_per_contig.append(int(pot_indel))
                    print pot_indels_per_contig
                    if len(sorted(pot_indels_per_contig)) < 2:
                        contig = ''.join(target_biosequence_final[int(pos_details[0])-1:int(pos_details[1])])
                        header_id = '>contig_' + str(contig_counter) + "_mapped to region_" + region
                        contig_fasta = SeqRecord(Seq(re.sub(r'[\*]','',contig)), id = header_id)
                        predicted_contig.append(contig_fasta)
                        updated_coverage_distribution.append(region)
                    elif len(sorted(pot_indels_per_contig)) > 1:
                            internal_del = []
                            for k, g in groupby(enumerate(sorted(pot_indels_per_contig)), lambda (i,x):i-x):
                                se_pos =  list(map(itemgetter(1), g))
                                if len(se_pos) == 2:
                                    internal_del.extend(se_pos)
                            large_indels_position_taken.extend(internal_del)
                            if len(internal_del) == 0:
                                contig = ''.join(target_biosequence_final[int(pos_details[0])-1:int(pos_details[1])])
                                header_id = '>contig_' + str(contig_counter) + "_mapped to region_" + region
                                contig_fasta = SeqRecord(Seq(re.sub(r'[\*]','',contig)), id = header_id)
                                predicted_contig.append(contig_fasta)
                                updated_coverage_distribution.append(region)
                            else:
                                pos_details.extend(internal_del)
                                updated_contig_pos = sorted([int(elem) for elem in pos_details])
                                updated_contig_pos_by_section = [updated_contig_pos[i:i+2] for i in range(0,len(updated_contig_pos),2)]
                                for updated_sections in updated_contig_pos_by_section:
                                    contig_counter += 1
                                    sub_region = str(updated_sections[0]) + "-" + str(updated_sections[1])
                                    contig = ''.join(target_biosequence_final[int(updated_contig_pos[0])-1:int(updated_contig_pos[1])])
                                    header_id = '>contig_' + str(contig_counter) + "_mapped to region_" + sub_region
                                    contig_fasta = SeqRecord(Seq(re.sub(r'[\*]','',contig)), id = header_id)
                                    predicted_contig.append(contig_fasta)
                                    updated_coverage_distribution.append(updated_sections)
                total_info = {}
                total_info['depth'] = str(average_depth) + ':' + str(min_depth) + ':' +  str(max_depth)
                total_info['coverage'] = ratio_coverage
                total_info['homology'] = homology
                total_info['probability_big_indels'] = positions_indels_probabilities
                total_info['position_deletions'] = position_deletions
                total_info['position_insertions'] = position_insertions
                total_info['position_nuc_mismatchs'] = position_mismatchs
                total_info['position_depth'] = positions_infos
                total_info['predicted_seq'] = predicted_contig
                total_info['positions_mix'] = positions_mix
                total_info['coverage_distribution'] = coverage_distribution
                total_info['sequence_distribution'] = updated_coverage_distribution
                total_info['position_with_coverage'] = positions_with_coverage
                pileup_hash[allele] = total_info
            else:
                pass
        else:
            pass
    return pileup_hash
