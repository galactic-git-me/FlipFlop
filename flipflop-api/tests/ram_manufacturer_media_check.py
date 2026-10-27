from app.services.component_media_identity import media_key,group_media_inventory
assert media_key('ram','Corsair Vengeance DDR4',1)==media_key('ram','CORSAIR DDR5 RAM',2)
assert media_key('ram','Corsair DDR5',1)!=media_key('ram','Crucial DDR5',2)
for title,key in [('G.SKILL Trident DDR5','ram_gskill'),('TEAMGROUP T-Force DDR4','ram_teamgroup'),('Kingston Fury DDR5','ram_kingston'),('Lexar DDR5','ram_lexar')]:
 assert media_key('ram',title,1)[1]==key
assert media_key('ram','Unbranded DDR5',1)[1]=='ram_unclassified'
rows=[dict(category='ram',title=t,listing_id=i,variant_id=i,variant_ids=[i]) for i,t in enumerate(['Corsair DDR4','Corsair DDR5','Crucial DDR5'],1)]
result=group_media_inventory(rows)
assert len(result)==2 and next(r for r in result if r['title']=='Corsair RAM')['product_count']==2
print('PASS: RAM grouped by manufacturer across DDR generations, separate brands, unknown brand held')
