UPDATE lead_entity SET signal=CASE signal WHEN 'icp_backlog' THEN 'qbcc_backlog' WHEN 'new' THEN 'qbcc_new'
 WHEN 'category_changed' THEN 'qbcc_category_changed' ELSE signal END WHERE source='qbcc';
UPDATE worklist_row SET selected_signal=CASE selected_signal WHEN 'icp_backlog' THEN 'qbcc_backlog' WHEN 'new' THEN 'qbcc_new'
 WHEN 'category_changed' THEN 'qbcc_category_changed' ELSE selected_signal END WHERE lead_id IN (SELECT lead_id FROM lead_entity WHERE source='qbcc');
